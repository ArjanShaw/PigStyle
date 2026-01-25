// streaming.js - Get genres from records, random start, YouTube only with voting

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

// SIMPLE VOTING SYSTEM
class VotingSystem {
    constructor() {
        this.apiBaseUrl = 'https://arjanshaw.pythonanywhere.com';
    }

    // Cast a vote and update UI immediately
    async castVote(recordId) {
        try {
            console.log('=== VOTE START ===');
            
            // ALWAYS get fresh elements - don't cache them
            const upvoteBtn = document.getElementById('upvoteBtn');
            const upvoteCountElement = document.getElementById('upvoteCount');
            
            console.log('Elements:', {
                upvoteBtn: upvoteBtn ? 'FOUND' : 'NOT FOUND',
                upvoteCountElement: upvoteCountElement ? 'FOUND' : 'NOT FOUND',
                currentCount: upvoteCountElement?.textContent
            });
            
            if (!upvoteBtn || !upvoteCountElement) {
                console.error('CRITICAL: Cannot find vote elements!');
                
                // Try alternative selectors
                const altBtn = document.querySelector('.upvote-btn');
                const altCount = document.querySelector('.upvote-count');
                console.log('Alternative:', {
                    altBtn: altBtn,
                    altCount: altCount
                });
                
                return false;
            }
            
            // Disable button immediately
            upvoteBtn.disabled = true;
            upvoteBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Voting...';
            
            // Make the vote request
            const response = await fetch(`${this.apiBaseUrl}/vote/${recordId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                }
            });

            const result = await response.json();
            console.log('API Response:', result);
            
            if (response.ok && result.status === 'success') {
                // ✅ SUCCESS: Update UI with vote_count from response
                const newCount = result.vote_count;
                upvoteCountElement.textContent = newCount;
                upvoteBtn.classList.add('voted');
                upvoteBtn.disabled = true;
                upvoteBtn.title = "Already voted";
                upvoteBtn.innerHTML = '<i class="fas fa-check"></i><span class="upvote-count">' + newCount + '</span>';
                
                userHasUpvoted = true;
                
                console.log('UI updated to:', newCount);
                this.showVoteFeedback('✓ Vote recorded! Votes: ' + newCount);
                return true;
                
            } else if (result.error === 'Already voted') {
                // Already voted - update with current count from response
                const currentCount = result.vote_count || 0;
                upvoteCountElement.textContent = currentCount;
                upvoteBtn.classList.add('voted');
                upvoteBtn.disabled = true;
                upvoteBtn.title = "Already voted";
                upvoteBtn.innerHTML = '<i class="fas fa-check"></i><span class="upvote-count">' + currentCount + '</span>';
                
                userHasUpvoted = true;
                
                this.showVoteFeedback('Already voted! Votes: ' + currentCount);
                return false;
                
            } else {
                // Other error
                upvoteBtn.disabled = false;
                upvoteBtn.innerHTML = '<i class="fas fa-thumbs-up"></i><span class="upvote-count">' + upvoteCountElement.textContent + '</span>';
                
                this.showVoteFeedback('Error: ' + (result.error || 'Vote failed'), false);
                return false;
            }
        } catch (error) {
            console.error('Vote error:', error);
            
            // Re-enable button on error
            const upvoteBtn = document.getElementById('upvoteBtn');
            const upvoteCountElement = document.getElementById('upvoteCount');
            if (upvoteBtn && upvoteCountElement) {
                upvoteBtn.disabled = false;
                upvoteBtn.innerHTML = '<i class="fas fa-thumbs-up"></i><span class="upvote-count">' + upvoteCountElement.textContent + '</span>';
            }
            
            this.showVoteFeedback('Network error', false);
            return false;
        }
    }

    showVoteFeedback(message, success = true) {
        // Remove any existing feedback
        const existing = document.getElementById('voteFeedback');
        if (existing) existing.remove();
        
        const feedbackEl = document.createElement('div');
        feedbackEl.id = 'voteFeedback';
        feedbackEl.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 12px 24px;
            border-radius: 8px;
            color: white;
            font-weight: bold;
            z-index: 10000;
            font-size: 16px;
            background: ${success ? '#27ae60' : '#e74c3c'};
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            animation: fadeIn 0.3s ease;
        `;
        
        feedbackEl.textContent = message;
        document.body.appendChild(feedbackEl);
        
        setTimeout(() => {
            feedbackEl.style.opacity = '0';
            feedbackEl.style.transition = 'opacity 0.5s';
            setTimeout(() => {
                if (feedbackEl.parentNode) feedbackEl.remove();
            }, 500);
        }, 3000);
    }

    setupVoteHandlers() {
        console.log('Setting up vote handlers...');
        
        // Get the button
        const upvoteBtn = document.getElementById('upvoteBtn');
        console.log('Found upvoteBtn:', upvoteBtn);
        
        if (upvoteBtn) {
            console.log('Attaching click handler...');
            
            upvoteBtn.addEventListener('click', (event) => {
                console.log('Button clicked!', {
                    currentRecordId: currentRecordId,
                    userHasUpvoted: userHasUpvoted,
                    eventTarget: event.target
                });
                
                if (currentRecordId && !userHasUpvoted) {
                    console.log('Calling castVote for:', currentRecordId);
                    this.castVote(currentRecordId);
                } else if (userHasUpvoted) {
                    this.showVoteFeedback('Already voted for this track!', false);
                }
            });
            
            console.log('Vote handler attached');
        } else {
            console.error('setupVoteHandlers: Could not find upvoteBtn!');
            console.log('Trying again in 1 second...');
            
            // Try again after a delay
            setTimeout(() => {
                const retryBtn = document.getElementById('upvoteBtn');
                console.log('Retry found upvoteBtn:', retryBtn);
                if (retryBtn) {
                    retryBtn.addEventListener('click', () => {
                        if (currentRecordId && !userHasUpvoted) {
                            this.castVote(currentRecordId);
                        }
                    });
                }
            }, 1000);
        }
    }
    
    // Update initial vote display when track loads
    async updateVoteDisplay(record) {
        if (!record) return;
        
        try {
            // Get initial votes from GET /votes endpoint
            const response = await fetch(`${this.apiBaseUrl}/votes`);
            if (response.ok) {
                const data = await response.json();
                if (data.status === 'success' && data.votes) {
                    const recordVotes = data.votes.find(v => v.record_id === record.id);
                    const voteCount = recordVotes ? recordVotes.vote_count : 0;
                    
                    const upvoteCountElement = document.getElementById('upvoteCount');
                    const upvoteBtn = document.getElementById('upvoteBtn');
                    
                    if (upvoteCountElement && upvoteBtn) {
                        upvoteCountElement.textContent = voteCount;
                        upvoteBtn.classList.remove('voted');
                        upvoteBtn.disabled = false;
                        userHasUpvoted = false;
                    }
                }
            }
        } catch (error) {
            console.error('Error loading initial votes:', error);
        }
    }
}

// Initialize voting system
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
    userHasUpvoted = false; // Reset for new track
    
    // Update vote display
    if (votingSystem && votingSystem.updateVoteDisplay) {
        votingSystem.updateVoteDisplay(currentRecord);
    }
    
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
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded, initializing...');
    
    // Setup UI
    setupUI();
    
    // Setup vote handlers
    votingSystem.setupVoteHandlers();
    
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