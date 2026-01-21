// streaming.js - Get genres from records, random start, YouTube only with upvotes only
// FIXED: votingSystem initialization order

console.log('streaming.js loaded!');

let allRecords = [];
let filteredRecords = [];
let currentTrackIndex = 0;
let youtubePlayer = null;
let youtubeAPILoaded = false;
let genreMap = {};

// Current record ID for voting
let currentRecordId = null;
let userHasUpvoted = false;

// Voting system with upvotes only
class VotingSystem {
    constructor() {
        this.apiBaseUrl = 'https://arjanshaw.pythonanywhere.com';
        this.userIP = null;
        this.userUpvotes = new Set(); // Cache of records the user has upvoted
    }

    async initialize() {
        await this.getUserIP();
        this.setupVoteHandlers();
        await this.loadUserUpvotes();
    }

    async getUserIP() {
        try {
            const response = await fetch('https://api.ipify.org?format=json');
            const data = await response.json();
            this.userIP = data.ip;
            console.log('User IP:', this.userIP);
        } catch (error) {
            console.error('Error getting IP:', error);
            this.userIP = 'unknown_' + Math.random().toString(36).substr(2, 9);
        }
    }

    async loadUserUpvotes() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/user-votes/${this.userIP}`);
            if (response.ok) {
                const data = await response.json();
                if (data.status === 'success' && data.votes) {
                    // Filter only upvotes from the user's votes
                    Object.entries(data.votes).forEach(([recordId, voteType]) => {
                        if (voteType === 'upvote') {
                            this.userUpvotes.add(parseInt(recordId));
                        }
                    });
                    console.log('Loaded user upvotes:', Array.from(this.userUpvotes));
                }
            } else {
                console.warn('Could not load user votes, endpoint might not exist');
            }
        } catch (error) {
            console.error('Error loading user upvotes:', error);
        }
    }

    // Use the correct endpoint /votes/{record_id}
    async fetchFreshVoteCount(recordId) {
        try {
            // Use the correct endpoint from your API: /votes/{record_id}
            const response = await fetch(`${this.apiBaseUrl}/votes/${recordId}`);
            if (response.ok) {
                const data = await response.json();
                if (data.status === 'success') {
                    // Your API returns: up_votes, down_votes, kill_votes
                    return data.up_votes || 0;
                }
            } else {
                console.warn(`Failed to fetch votes for record ${recordId}:`, response.status);
            }
        } catch (error) {
            console.error('Error fetching fresh vote count:', error);
        }
        return null; // Return null if fetch fails
    }

    async updateVoteDisplay(record) {
        if (!record) return;
        
        const upvoteCountElement = document.getElementById('upvoteCount');
        const upvoteBtn = document.getElementById('upvoteBtn');
        
        if (upvoteCountElement) {
            // FIRST: Try to get fresh count from API
            const freshCount = await this.fetchFreshVoteCount(record.id);
            
            if (freshCount !== null) {
                // Use fresh count from API
                upvoteCountElement.textContent = freshCount;
                // Also update the local record cache
                if (record) {
                    record.up_votes = freshCount;
                }
            } else {
                // Fallback to local cached count
                upvoteCountElement.textContent = record.up_votes || 0;
            }
        }
        
        // Update button state based on whether user has upvoted
        this.updateUpvoteButtonState(record.id);
    }

    updateUpvoteButtonState(recordId) {
        const upvoteBtn = document.getElementById('upvoteBtn');
        
        if (!upvoteBtn) return;
        
        // Check if user has upvoted this record
        const hasUpvoted = this.userUpvotes.has(recordId);
        userHasUpvoted = hasUpvoted;
        
        // Update button appearance
        if (hasUpvoted) {
            upvoteBtn.classList.add('active');
            upvoteBtn.title = "Remove upvote";
        } else {
            upvoteBtn.classList.remove('active');
            upvoteBtn.title = "Upvote";
        }
    }

    showVoteFeedback(message, success = true) {
        const feedbackEl = document.createElement('div');
        feedbackEl.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 10px 20px;
            border-radius: 5px;
            color: white;
            font-weight: bold;
            z-index: 1000;
            transition: opacity 0.3s;
            background: ${success ? '#27ae60' : '#e74c3c'};
        `;
        
        feedbackEl.textContent = message;
        
        document.body.appendChild(feedbackEl);
        
        setTimeout(() => {
            feedbackEl.style.opacity = '0';
            setTimeout(() => {
                if (feedbackEl.parentNode) {
                    feedbackEl.remove();
                }
            }, 300);
        }, 2000);
    }

    async toggleUpvote(recordId) {
        try {
            if (!recordId) {
                console.error('No record ID for voting');
                return false;
            }

            const hasUpvoted = this.userUpvotes.has(recordId);
            const voteType = hasUpvoted ? 'remove' : 'upvote';

            // Your API doesn't support 'remove' vote type
            // According to your API, vote_type must be 'upvote', 'downvote', or 'kill'
            // So we need to handle remove differently
            let actualVoteType;
            if (hasUpvoted) {
                // To remove an upvote, we might need a different approach
                // Your API doesn't support removing votes, so we'll skip the vote
                // and just update locally
                console.log('Cannot remove vote - API only supports adding votes');
                return false;
            } else {
                actualVoteType = 'upvote';
            }

            const response = await fetch(`${this.apiBaseUrl}/vote/${recordId}/${this.userIP}/${actualVoteType}`, {
                method: 'POST'
            });

            const data = await response.json();
            
            if (data && data.status === 'success') {
                // Update local upvote cache
                if (hasUpvoted) {
                    this.userUpvotes.delete(recordId);
                } else {
                    this.userUpvotes.add(recordId);
                }
                
                // CRITICAL FIX: Fetch fresh count from API after voting
                const freshCount = await this.fetchFreshVoteCount(recordId);
                
                // Update local record data
                if (filteredRecords.length > 0 && currentTrackIndex < filteredRecords.length) {
                    const record = filteredRecords[currentTrackIndex];
                    if (record.id === recordId) {
                        // Use fresh count from API
                        if (freshCount !== null) {
                            record.up_votes = freshCount;
                        } else {
                            // Fallback: increment locally if fresh count failed
                            if (!hasUpvoted) {
                                record.up_votes = (record.up_votes || 0) + 1;
                            }
                        }
                        this.updateVoteDisplay(record);
                    }
                }
                
                this.showVoteFeedback(hasUpvoted ? 'Upvote removed (local only)' : '✓ Upvoted!');
                return true;
            } else {
                this.showVoteFeedback(data?.error || 'Vote failed', false);
                return false;
            }
        } catch (error) {
            console.error('Error recording vote:', error);
            this.showVoteFeedback('Network error', false);
            return false;
        }
    }

    setupVoteHandlers() {
        const upvoteBtn = document.getElementById('upvoteBtn');
        
        if (upvoteBtn) {
            upvoteBtn.addEventListener('click', () => {
                if (currentRecordId) {
                    this.toggleUpvote(currentRecordId);
                }
            });
        }
    }
}

// FIX: Initialize votingSystem here, not in DOMContentLoaded
let votingSystem = new VotingSystem();

// Load YouTube IFrame API
function loadYouTubeAPI() {
    if (window.YT && window.YT.Player) {
        youtubeAPILoaded = true;
        console.log('YouTube API already loaded');
        return;
    }
    
    const tag = document.createElement('script');
    tag.src = 'https://www.youtube.com/iframe_api';
    const firstScriptTag = document.getElementsByTagName('script')[0];
    firstScriptTag.parentNode.insertBefore(tag, firstScriptTag);
    
    console.log('Loading YouTube API...');
}

// This function is called by YouTube API when ready
window.onYouTubeIframeAPIReady = function() {
    youtubeAPILoaded = true;
    console.log('YouTube API ready!');
    
    if (filteredRecords.length > 0) {
        loadCurrentYouTubeTrack();
    }
};

// Load saved selections from localStorage
function loadSavedSelections() {
    const savedGenre = localStorage.getItem('pigstyleStreamingGenre');
    
    if (savedGenre) {
        document.getElementById('genreFilter').value = savedGenre;
    }
    
    console.log('Loaded saved selections:', { genre: savedGenre });
}

// Save selections to localStorage
function saveSelections() {
    const genre = document.getElementById('genreFilter').value;
    
    localStorage.setItem('pigstyleStreamingGenre', genre);
    
    console.log('Saved selections:', { genre });
}

// Main function to start playing based on current selections
function startPlaying() {
    const genreId = document.getElementById('genreFilter').value;
    const genreName = genreId ? (genreMap[genreId] || 'Selected Genre') : 'All Genres';
    
    console.log(`Starting YouTube playback - Genre: ${genreName}`);
    
    // Save selections
    saveSelections();
    
    startYouTubePlayback(genreId);
}

// Start YouTube playback
function startYouTubePlayback(genreId) {
    console.log('Starting YouTube playback for genre:', genreId || 'All');
    
    if (youtubePlayer) {
        youtubePlayer.destroy();
        youtubePlayer = null;
    }
    
    document.getElementById('loading').style.display = 'none';
    document.getElementById('playerContent').style.display = 'block';
    
    // Show YouTube player and controls
    document.getElementById('youtubeContainer').style.display = 'block';
    document.getElementById('youtubeControls').style.display = 'flex';
    document.getElementById('controlsRow').style.display = 'flex';
    
    if (!youtubeAPILoaded) {
        loadYouTubeAPI();
    }
    
    // Apply genre filter for YouTube
    if (!genreId) {
        // Show all records with YouTube URLs
        filteredRecords = allRecords.filter(record => 
            record.youtube_url && 
            (record.youtube_url.includes('youtube.com') || 
             record.youtube_url.includes('youtu.be'))
        );
    } else {
        // Filter by genre
        filteredRecords = allRecords.filter(record => 
            record.youtube_url && 
            (record.youtube_url.includes('youtube.com') || 
             record.youtube_url.includes('youtu.be')) &&
            record.genre_id == genreId
        );
    }
    
    console.log(`Filtered to ${filteredRecords.length} records for YouTube playback`);
    
    if (filteredRecords.length > 0) {
        // Random start when filtering
        currentTrackIndex = Math.floor(Math.random() * filteredRecords.length);
        console.log(`Random start at index: ${currentTrackIndex}/${filteredRecords.length}`);
        
        if (youtubeAPILoaded) {
            loadCurrentYouTubeTrack();
        } else {
            document.getElementById('youtube-player').innerHTML = `
                <div style="padding: 40px; text-align: center; color: white;">
                    <h3>Loading YouTube Player...</h3>
                    <p>Please wait a moment...</p>
                </div>
            `;
        }
    } else {
        document.getElementById('youtube-player').innerHTML = `
            <div style="padding: 40px; text-align: center; color: white;">
                <h3>No Tracks Found</h3>
                <p>No YouTube videos found for ${genreMap[genreId] || 'this genre'}.</p>
            </div>
        `;
    }
}

// Load current YouTube track
function loadCurrentYouTubeTrack() {
    if (filteredRecords.length === 0) return;
    
    const currentRecord = filteredRecords[currentTrackIndex];
    const youtubeId = extractYouTubeId(currentRecord.youtube_url);
    
    console.log('Loading track:', currentRecord.artist, '-', currentRecord.title);
    console.log('YouTube ID:', youtubeId);
    console.log('Current index:', currentTrackIndex, '/', filteredRecords.length);
    
    // Update track info
    document.getElementById('trackTitle').textContent = currentRecord.title || 'Unknown Title';
    document.getElementById('trackArtist').textContent = currentRecord.artist || 'Unknown Artist';
    
    // Update price
    const priceElement = document.getElementById('trackPrice');
    if (priceElement && currentRecord.store_price) {
        priceElement.textContent = `$${parseFloat(currentRecord.store_price).toFixed(2)}`;
    }
    
    // Set current record ID for voting
    currentRecordId = currentRecord.id;
    
    // Update vote display - THIS NOW FETCHES FRESH DATA
    votingSystem.updateVoteDisplay(currentRecord);
    
    if (!youtubeId) {
        document.getElementById('youtube-player').innerHTML = `
            <div style="padding: 40px; text-align: center; color: white;">
                <h3>No YouTube Video Available</h3>
                <p>Track: ${currentRecord.artist} - ${currentRecord.title}</p>
                <p>YouTube URL: ${currentRecord.youtube_url || 'None'}</p>
                <div style="margin-top: 20px;">
                    <button onclick="playNextTrack()" style="padding: 10px 20px; margin: 10px; background: #f0f0f0; color: #333; border: none; border-radius: 5px;">
                        Next Track
                    </button>
                </div>
            </div>
        `;
        
        setTimeout(playNextTrack, 10000);
        return;
    }
    
    document.getElementById('youtube-player').innerHTML = '<div id="player"></div>';
    
    youtubePlayer = new YT.Player('player', {
        height: '100%',
        width: '100%',
        videoId: youtubeId,
        playerVars: {
            'autoplay': 1,
            'controls': 1,
            'rel': 0,
            'modestbranding': 1,
            'showinfo': 0
        },
        events: {
            'onReady': onPlayerReady,
            'onStateChange': onPlayerStateChange,
            'onError': onPlayerError
        }
    });
}

// YouTube player ready callback
function onPlayerReady(event) {
    console.log('YouTube player ready');
    event.target.playVideo();
}

// YouTube player state change callback
function onPlayerStateChange(event) {
    if (event.data === 0) { // ENDED
        console.log('Video ended, playing next track...');
        playNextTrack();
    }
    
    if (event.data === 1) { // PLAYING
        console.log('Video started playing');
    }
}

// YouTube player error callback
function onPlayerError(event) {
    console.error('YouTube player error:', event.data);
    setTimeout(playNextTrack, 3000);
}

// Extract YouTube ID from URL
function extractYouTubeId(url) {
    if (!url) return null;
    
    const patterns = [
        /youtube\.com\/watch\?v=([a-zA-Z0-9_-]{11})/,
        /youtu\.be\/([a-zA-Z0-9_-]{11})/,
        /youtube\.com\/embed\/([a-zA-Z0-9_-]{11})/,
        /youtube\.com\/v\/([a-zA-Z0-9_-]{11})/
    ];
    
    for (const pattern of patterns) {
        const match = url.match(pattern);
        if (match && match[1]) {
            return match[1];
        }
    }
    
    return null;
}

// Play previous track
function playPreviousTrack() {
    if (filteredRecords.length === 0) return;
    
    currentTrackIndex = (currentTrackIndex - 1 + filteredRecords.length) % filteredRecords.length;
    console.log('Playing previous track, new index:', currentTrackIndex);
    loadCurrentYouTubeTrack();
}

// Play next track
function playNextTrack() {
    if (filteredRecords.length === 0) return;
    
    currentTrackIndex = (currentTrackIndex + 1) % filteredRecords.length;
    console.log('Playing next track, new index:', currentTrackIndex);
    loadCurrentYouTubeTrack();
}

// Build genre map from records
function buildGenreMap(records) {
    genreMap = {};
    
    // Find unique genre IDs and names from records
    records.forEach(record => {
        if (record.genre_id && record.genre_name && !genreMap[record.genre_id]) {
            // Use the actual genre name from the JOIN
            genreMap[record.genre_id] = record.genre_name;
        } else if (record.genre_id && !genreMap[record.genre_id]) {
            // Fallback if no genre name
            genreMap[record.genre_id] = `Genre ${record.genre_id}`;
        }
    });
    
    console.log('Built genre map from records:', genreMap);
}

// Populate genre filter dropdown
function populateGenreFilter() {
    const genreFilter = document.getElementById('genreFilter');
    
    // Clear existing options except "All Genres"
    while (genreFilter.options.length > 1) {
        genreFilter.remove(1);
    }
    
    // Add genre options sorted by ID
    const sortedGenres = Object.entries(genreMap)
        .sort((a, b) => parseInt(a[0]) - parseInt(b[0]));
    
    sortedGenres.forEach(([id, name]) => {
        const option = document.createElement('option');
        option.value = id;
        option.textContent = name;
        genreFilter.appendChild(option);
    });
    
    console.log(`Populated ${sortedGenres.length} genres in filter`);
}

// Load records from API
async function loadRecordsFromAPI() {
    try {
        console.log('Loading records from API...');
        
        const response = await fetch('https://arjanshaw.pythonanywhere.com/records?limit=100');
        
        if (!response.ok) {
            throw new Error(`API error: ${response.status} ${response.statusText}`);
        }
        
        const data = await response.json();
        
        if (data && data.status === 'success' && data.records) {
            allRecords = data.records;
            console.log(`Loaded ${allRecords.length} records from API`);
            
            // Build genre map from records
            buildGenreMap(allRecords);
            
            // Populate genre filter
            populateGenreFilter();
            
            // Load saved selections
            loadSavedSelections();
            
            // Start playing based on current selections
            startPlaying();
            
        } else {
            throw new Error('Invalid response from API');
        }
        
    } catch (error) {
        console.error('Error loading records from API:', error);
        document.getElementById('youtube-player').innerHTML = `
            <div style="padding: 40px; text-align: center; color: white;">
                <h3>Error Loading Records</h3>
                <p>Failed to load from API: ${error.message}</p>
                <p>Make sure your API server at arjanshaw.pythonanywhere.com is running.</p>
            </div>
        `;
    }
}

// Setup UI
function setupUI() {
    const genreFilter = document.getElementById('genreFilter');
    
    if (genreFilter) {
        genreFilter.addEventListener('change', function() {
            console.log('Genre changed to:', this.value);
            startPlaying();
        });
    }
    
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    
    if (prevBtn) prevBtn.addEventListener('click', playPreviousTrack);
    if (nextBtn) nextBtn.addEventListener('click', playNextTrack);
}

// Manual scaling functionality
let currentScale = 1;

function scaleDown() {
    if (currentScale > 0.5) {
        currentScale -= 0.1;
        applyScale();
    }
}

function scaleUp() {
    if (currentScale < 2.0) {
        currentScale += 0.1;
        applyScale();
    }
}

function resetScale() {
    currentScale = 1;
    applyScale();
}

function applyScale() {
    const playerContainer = document.querySelector('.player-container');
    
    if (playerContainer) {
        playerContainer.style.transform = `scale(${currentScale})`;
        playerContainer.style.transformOrigin = 'center';
    }
    
    // Update scale percentage display
    const scalePercent = document.getElementById('scalePercent');
    if (scalePercent) {
        scalePercent.textContent = `${Math.round(currentScale * 100)}%`;
    }
    
    // Save scale preference
    localStorage.setItem('pigstyleStreamingScale', currentScale);
}

// Load saved scale on startup
function loadSavedScale() {
    const savedScale = localStorage.getItem('pigstyleStreamingScale');
    if (savedScale) {
        currentScale = parseFloat(savedScale);
        // Limit scale to reasonable bounds
        currentScale = Math.max(0.5, Math.min(2.0, currentScale));
        setTimeout(() => applyScale(), 500);
    }
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', async function() {
    console.log('DOM loaded, initializing...');
    
    // Setup UI
    setupUI();
    
    // Initialize voting system - FIXED: This is now safe to call
    await votingSystem.initialize();
    
    // Load YouTube API
    loadYouTubeAPI();
    
    // Load saved scale
    loadSavedScale();
    
    // Load records and start playing
    setTimeout(loadRecordsFromAPI, 500);
});

// Make functions available globally
window.playPreviousTrack = playPreviousTrack;
window.playNextTrack = playNextTrack;
window.startPlaying = startPlaying;
window.scaleDown = scaleDown;
window.scaleUp = scaleUp;
window.resetScale = resetScale;