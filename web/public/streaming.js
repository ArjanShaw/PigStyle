// streaming.js - Get genres from records, random start, no condition stars

console.log('streaming.js loaded!');

let allRecords = [];
let filteredRecords = [];
let currentTrackIndex = 0;
let currentStreamingService = 'youtube';
let youtubePlayer = null;
let youtubeAPILoaded = false;
let genreMap = {};

// Voting system
class VotingSystem {
    constructor() {
        this.apiBaseUrl = 'https://arjanshaw.pythonanywhere.com';
        this.voteCounts = {};
        this.userIP = null;
    }

    async initialize() {
        await this.getUserIP();
        await this.loadAllVoteCounts();
        this.setupVoteHandlers();
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

    async loadAllVoteCounts() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/records?limit=1000`);
            const data = await response.json();
            
            if (data && data.records) {
                data.records.forEach(record => {
                    const trackId = `${record.artist} - ${record.title}`;
                    this.voteCounts[trackId] = {
                        upvotes: record.upvotes || 0,
                        downvotes: record.downvotes || 0
                    };
                });
                console.log('Loaded vote counts from API');
                this.updateAllVoteDisplays();
            } else {
                console.error('Failed to load vote counts from API');
            }
        } catch (error) {
            console.error('Error loading vote counts from API:', error);
        }
    }

    updateVoteDisplay(artistTitle) {
        const counts = this.voteCounts[artistTitle] || { upvotes: 0, downvotes: 0 };
        
        const upvoteCount = document.getElementById('upvoteCount');
        const downvoteCount = document.getElementById('downvoteCount');
        
        if (upvoteCount) upvoteCount.textContent = counts.upvotes;
        if (downvoteCount) downvoteCount.textContent = counts.downvotes;
    }

    updateAllVoteDisplays() {
        if (filteredRecords.length > 0 && currentTrackIndex < filteredRecords.length) {
            const currentRecord = filteredRecords[currentTrackIndex];
            const trackId = `${currentRecord.artist} - ${currentRecord.title}`;
            this.updateVoteDisplay(trackId);
        }
    }

    showVoteFeedback(artistTitle, voteType, success, errorMessage = '') {
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
        
        if (success) {
            feedbackEl.textContent = `✓ ${voteType === 'upvote' ? 'Liked!' : 'Disliked!'}`;
        } else {
            feedbackEl.textContent = errorMessage || 'Vote failed';
        }
        
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

    async vote(artistTitle, voteType) {
        try {
            const [artist, ...titleParts] = artistTitle.split(' - ');
            const title = titleParts.join(' - ');
            
            const recordsResponse = await fetch(`${this.apiBaseUrl}/records?limit=1000`);
            const recordsData = await recordsResponse.json();
            
            let recordId = null;
            if (recordsData && recordsData.records) {
                const record = recordsData.records.find(r => 
                    r.artist === artist && r.title === title
                );
                if (record) {
                    recordId = record.id;
                }
            }
            
            if (!recordId) {
                console.error('Record not found for voting:', artistTitle);
                return false;
            }

            const response = await fetch(`${this.apiBaseUrl}/vote/${recordId}/${this.userIP}/${voteType}`, {
                method: 'POST'
            });

            const data = await response.json();
            
            if (data && data.status === 'success') {
                await this.loadAllVoteCounts();
                this.showVoteFeedback(artistTitle, voteType, true);
                return true;
            } else {
                this.showVoteFeedback(artistTitle, voteType, false, data?.error || 'Vote failed');
                return false;
            }
        } catch (error) {
            console.error('Error recording vote:', error);
            this.showVoteFeedback(artistTitle, voteType, false, 'Network error');
            return false;
        }
    }

    setupVoteHandlers() {
        const upvoteBtn = document.getElementById('upvoteBtn');
        const downvoteBtn = document.getElementById('downvoteBtn');
        
        if (upvoteBtn) {
            upvoteBtn.addEventListener('click', () => {
                if (filteredRecords.length > 0 && currentTrackIndex < filteredRecords.length) {
                    const currentRecord = filteredRecords[currentTrackIndex];
                    const trackId = `${currentRecord.artist} - ${currentRecord.title}`;
                    this.vote(trackId, 'upvote');
                }
            });
        }
        
        if (downvoteBtn) {
            downvoteBtn.addEventListener('click', () => {
                if (filteredRecords.length > 0 && currentTrackIndex < filteredRecords.length) {
                    const currentRecord = filteredRecords[currentTrackIndex];
                    const trackId = `${currentRecord.artist} - ${currentRecord.title}`;
                    this.vote(trackId, 'downvote');
                }
            });
        }
    }
}

// Initialize voting system
const votingSystem = new VotingSystem();

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
    
    if (currentStreamingService === 'youtube' && filteredRecords.length > 0) {
        loadCurrentYouTubeTrack();
    }
};

// Show Spotify player
function showSpotifyPlayer() {
    console.log('Showing Spotify player');
    
    if (youtubePlayer) {
        youtubePlayer.destroy();
        youtubePlayer = null;
    }
    
    document.getElementById('loading').style.display = 'none';
    document.getElementById('playerContent').style.display = 'block';
    
    document.getElementById('spotifyContainer').style.display = 'block';
    document.getElementById('youtubeContainer').style.display = 'none';
    document.getElementById('spotifyControls').style.display = 'flex';
    document.getElementById('youtubeControls').style.display = 'none';
    
    const embed = document.getElementById('spotifyPlaylistEmbed');
    embed.src = 'https://open.spotify.com/embed/playlist/72RkLX9Hhy5LZcaUTNSj60?utm_source=generator&theme=0';
    
    document.getElementById('trackTitle').textContent = 'PigStyle Records Collection';
    document.getElementById('trackArtist').textContent = 'Various Artists';
    document.getElementById('trackPrice').textContent = 'Stream Now';
}

// Show YouTube player
function showYouTubePlayer() {
    console.log('Showing YouTube player');
    
    document.getElementById('loading').style.display = 'none';
    document.getElementById('playerContent').style.display = 'block';
    
    document.getElementById('youtubeContainer').style.display = 'block';
    document.getElementById('spotifyContainer').style.display = 'none';
    document.getElementById('youtubeControls').style.display = 'flex';
    document.getElementById('spotifyControls').style.display = 'none';
    
    if (!youtubeAPILoaded) {
        loadYouTubeAPI();
    }
    
    loadRecordsFromAPI();
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
            
            // Filter for records with YouTube URLs
            filteredRecords = allRecords.filter(record => 
                record.youtube_url && 
                (record.youtube_url.includes('youtube.com') || 
                 record.youtube_url.includes('youtu.be'))
            );
            
            console.log(`Found ${filteredRecords.length} records with YouTube URLs`);
            
            if (filteredRecords.length > 0) {
                // RANDOM START: Pick random track
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
                        <h3>No YouTube Videos Found</h3>
                        <p>Loaded ${allRecords.length} records from API, but none have YouTube URLs.</p>
                        <p>Add YouTube URLs to your records in the database.</p>
                        <div style="margin-top: 20px;">
                            <button onclick="showSpotifyPlayer()" style="padding: 10px 20px; background: #1DB954; color: white; border: none; border-radius: 5px;">
                                Switch to Spotify
                            </button>
                        </div>
                    </div>
                `;
            }
            
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
                <div style="margin-top: 20px;">
                    <button onclick="showSpotifyPlayer()" style="padding: 10px 20px; background: #1DB954; color: white; border: none; border-radius: 5px;">
                        Switch to Spotify
                    </button>
                </div>
            </div>
        `;
    }
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
    
    // Set up event listener - FIXED: Only apply genre filter for YouTube
    genreFilter.addEventListener('change', function() {
        if (currentStreamingService === 'youtube') {
            applyGenreFilter(this.value);
        } else {
            showSpotifyGenreNotAvailable(this.value);
        }
    });
}

// Show error message for Spotify genre selection
function showSpotifyGenreNotAvailable(genreId) {
    const genreName = genreId ? (genreMap[genreId] || 'Selected Genre') : 'All Genres';
    
    document.getElementById('spotifyPlaylistEmbed').src = '';
    document.getElementById('spotifyContainer').innerHTML = `
        <div style="padding: 40px; text-align: center; color: white;">
            <h3>⏳ Genre Playlist Coming Soon</h3>
            <p>The Spotify playlist for <strong>${genreName}</strong> is not available yet.</p>
            <p>We're working on creating dedicated Spotify playlists for each genre.</p>
            <p>For now, you can enjoy our main PigStyle Records collection on Spotify.</p>
            <div style="margin-top: 20px;">
                <button onclick="resetToMainSpotifyPlaylist()" style="padding: 10px 20px; background: #1DB954; color: white; border: none; border-radius: 5px; margin: 5px;">
                    Back to Main Spotify Playlist
                </button>
                <button onclick="switchToYouTube()" style="padding: 10px 20px; background: #FF0000; color: white; border: none; border-radius: 5px; margin: 5px;">
                    Switch to YouTube for Genre Selection
                </button>
            </div>
        </div>
    `;
    
    // Reset genre filter to "All Genres"
    document.getElementById('genreFilter').value = '';
    
    // Update track info
    document.getElementById('trackTitle').textContent = 'Genre Playlist Coming Soon';
    document.getElementById('trackArtist').textContent = `${genreName} - Spotify`;
    document.getElementById('trackPrice').textContent = 'In Development';
}

// Reset to main Spotify playlist
function resetToMainSpotifyPlaylist() {
    showSpotifyPlayer();
}

// Switch to YouTube mode
function switchToYouTube() {
    document.getElementById('streamingService').value = 'youtube';
    currentStreamingService = 'youtube';
    showYouTubePlayer();
}

// Apply genre filter for YouTube
function applyGenreFilter(genreId) {
    if (currentStreamingService !== 'youtube') {
        return; // Only apply for YouTube
    }
    
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
    
    const genreName = genreId ? genreMap[genreId] : 'All';
    console.log(`Filtered to ${filteredRecords.length} records for genre: ${genreName}`);
    
    if (filteredRecords.length > 0) {
        // Random start when filtering
        currentTrackIndex = Math.floor(Math.random() * filteredRecords.length);
        console.log(`Random start at index: ${currentTrackIndex}/${filteredRecords.length}`);
        loadCurrentYouTubeTrack();
    } else {
        document.getElementById('youtube-player').innerHTML = `
            <div style="padding: 40px; text-align: center; color: white;">
                <h3>No Tracks Found</h3>
                <p>No YouTube videos found for ${genreName}.</p>
                <div style="margin-top: 20px;">
                    <button onclick="document.getElementById('genreFilter').value=''; applyGenreFilter('');" 
                            style="padding: 10px 20px; background: #f0f0f0; color: #333; border: none; border-radius: 5px;">
                        Show All Genres
                    </button>
                </div>
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
    document.getElementById('trackPrice').textContent = currentRecord.store_price ? 
        `$${parseFloat(currentRecord.store_price).toFixed(2)}` : 'Price N/A';
    
    // Update vote display
    const trackId = `${currentRecord.artist} - ${currentRecord.title}`;
    votingSystem.updateVoteDisplay(trackId);
    
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

// Setup service selector and other UI
function setupUI() {
    const selector = document.getElementById('streamingService');
    if (selector) {
        selector.addEventListener('change', function(e) {
            currentStreamingService = e.target.value;
            console.log('Switching to:', currentStreamingService);
            
            // Reset genre filter when switching services
            document.getElementById('genreFilter').value = '';
            
            if (currentStreamingService === 'youtube') {
                showYouTubePlayer();
            } else {
                showSpotifyPlayer();
            }
        });
    }
    
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    
    if (prevBtn) prevBtn.addEventListener('click', playPreviousTrack);
    if (nextBtn) nextBtn.addEventListener('click', playNextTrack);
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', async function() {
    console.log('DOM loaded, initializing...');
    
    // Setup UI
    setupUI();
    
    // Initialize voting system
    await votingSystem.initialize();
    
    // Load YouTube API
    loadYouTubeAPI();
    
    // Start with YouTube mode (default)
    setTimeout(showYouTubePlayer, 500);
});

// Make functions available globally
window.playPreviousTrack = playPreviousTrack;
window.playNextTrack = playNextTrack;
window.showSpotifyPlayer = showSpotifyPlayer;
window.resetToMainSpotifyPlaylist = resetToMainSpotifyPlaylist;
window.switchToYouTube = switchToYouTube;
window.showSpotifyGenreNotAvailable = showSpotifyGenreNotAvailable;