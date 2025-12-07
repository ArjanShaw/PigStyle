// streaming.js - Get genres from records, random start, no condition stars
// Now includes Spotify album art visualizer feature

console.log('streaming.js loaded!');

let allRecords = [];
let filteredRecords = [];
let currentTrackIndex = 0;
let currentStreamingService = 'youtube';
let youtubePlayer = null;
let youtubeAPILoaded = false;
let genreMap = {};
let spotifyPlaylists = [];
let currentSpotifyPlaylistId = null;

// Spotify Visualizer Variables
let spotifyVisualizerActive = false;
let spotifyVisualizerTimer = null;
let spotifyVisualizerStartTime = null;
let spotifyVisualizerCurrentTime = 0;
let spotifyPlaylistTracks = [];
let spotifyVisualizerCurrentTrackIndex = 0;
let spotifyVisualizerCumulativeTimes = [];
let spotifyVisualizerPaused = false;
let spotifyVisualizerMuted = false;

// Current record ID for voting
let currentRecordId = null;
let currentUserVote = null; // 'upvote', 'downvote', or 'kill'

// Voting system with improved tracking
class VotingSystem {
    constructor() {
        this.apiBaseUrl = 'https://arjanshaw.pythonanywhere.com';
        this.userIP = null;
        this.userVotes = {}; // Cache of user's votes: {recordId: voteType}
    }

    async initialize() {
        await this.getUserIP();
        this.setupVoteHandlers();
        await this.loadUserVotes();
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

    async loadUserVotes() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/user-votes/${this.userIP}`);
            if (response.ok) {
                const data = await response.json();
                if (data.status === 'success' && data.votes) {
                    this.userVotes = data.votes;
                    console.log('Loaded user votes:', this.userVotes);
                }
            }
        } catch (error) {
            console.error('Error loading user votes:', error);
        }
    }

    updateVoteDisplay(record) {
        if (!record) return;
        
        const votesElement = document.getElementById('votesCount');
        
        if (votesElement) {
            // Calculate net votes (upvotes - downvotes)
            const netVotes = (record.up_votes || 0) - (record.down_votes || 0);
            votesElement.textContent = netVotes;
        }
        
        // Update button states based on user's vote
        this.updateVoteButtonStates();
    }

    updateVoteButtonStates() {
        if (!currentRecordId) return;
        
        const upvoteBtn = document.getElementById('upvoteBtn');
        const downvoteBtn = document.getElementById('downvoteBtn');
        const killBtn = document.getElementById('killBtn');
        
        // Get user's vote for current record
        const userVote = this.userVotes[currentRecordId];
        
        // Reset all buttons
        if (upvoteBtn) upvoteBtn.classList.remove('active');
        if (downvoteBtn) downvoteBtn.classList.remove('active');
        if (killBtn) killBtn.classList.remove('active');
        
        // Set active state for current vote
        if (userVote === 'upvote' && upvoteBtn) {
            upvoteBtn.classList.add('active');
        } else if (userVote === 'downvote' && downvoteBtn) {
            downvoteBtn.classList.add('active');
        } else if (userVote === 'kill' && killBtn) {
            killBtn.classList.add('active');
        }
        
        // Update session variable
        currentUserVote = userVote;
    }

    showVoteFeedback(voteType, success, errorMessage = '') {
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
            if (voteType === 'upvote') {
                feedbackEl.textContent = '✓ Upvoted!';
            } else if (voteType === 'downvote') {
                feedbackEl.textContent = '✓ Downvoted!';
            } else if (voteType === 'kill') {
                feedbackEl.textContent = '✓ Removed from playlists!';
            }
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

    async vote(recordId, voteType) {
        try {
            if (!recordId) {
                console.error('No record ID for voting');
                return false;
            }

            const response = await fetch(`${this.apiBaseUrl}/vote/${recordId}/${this.userIP}/${voteType}`, {
                method: 'POST'
            });

            const data = await response.json();
            
            if (data && data.status === 'success') {
                // Update local vote cache
                this.userVotes[recordId] = voteType;
                
                // Update local record data if available
                if (currentStreamingService === 'youtube' && filteredRecords.length > 0 && currentTrackIndex < filteredRecords.length) {
                    const record = filteredRecords[currentTrackIndex];
                    if (record.id === recordId) {
                        if (voteType === 'upvote') {
                            record.up_votes = (record.up_votes || 0) + 1;
                        } else if (voteType === 'downvote') {
                            record.down_votes = (record.down_votes || 0) + 1;
                        } else if (voteType === 'kill') {
                            record.kill_votes = (record.kill_votes || 0) + 1;
                        }
                        this.updateVoteDisplay(record);
                    }
                }
                
                // Update button states
                this.updateVoteButtonStates();
                
                this.showVoteFeedback(voteType, true);
                return true;
            } else {
                this.showVoteFeedback(voteType, false, data?.error || 'Vote failed');
                return false;
            }
        } catch (error) {
            console.error('Error recording vote:', error);
            this.showVoteFeedback(voteType, false, 'Network error');
            return false;
        }
    }

    setupVoteHandlers() {
        const upvoteBtn = document.getElementById('upvoteBtn');
        const downvoteBtn = document.getElementById('downvoteBtn');
        const killBtn = document.getElementById('killBtn');
        
        if (upvoteBtn) {
            upvoteBtn.addEventListener('click', () => {
                if (currentRecordId) {
                    this.vote(currentRecordId, 'upvote');
                }
            });
        }
        
        if (downvoteBtn) {
            downvoteBtn.addEventListener('click', () => {
                if (currentRecordId) {
                    this.vote(currentRecordId, 'downvote');
                }
            });
        }
        
        if (killBtn) {
            killBtn.addEventListener('click', () => {
                if (currentRecordId) {
                    this.vote(currentRecordId, 'kill');
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

// Load saved selections from localStorage
function loadSavedSelections() {
    const savedService = localStorage.getItem('pigstyleStreamingService');
    const savedGenre = localStorage.getItem('pigstyleStreamingGenre');
    
    if (savedService) {
        currentStreamingService = savedService;
        updateServiceIcons(savedService);
    }
    
    if (savedGenre) {
        document.getElementById('genreFilter').value = savedGenre;
    }
    
    console.log('Loaded saved selections:', { service: savedService, genre: savedGenre });
}

// Update service icons active state
function updateServiceIcons(service) {
    const youtubeIcon = document.getElementById('youtubeIcon');
    const spotifyIcon = document.getElementById('spotifyIcon');
    
    if (youtubeIcon) youtubeIcon.classList.remove('active');
    if (spotifyIcon) spotifyIcon.classList.remove('active');
    
    if (service === 'youtube' && youtubeIcon) {
        youtubeIcon.classList.add('active');
    } else if (service === 'spotify' && spotifyIcon) {
        spotifyIcon.classList.add('active');
    }
}

// Save selections to localStorage
function saveSelections() {
    const service = currentStreamingService;
    const genre = document.getElementById('genreFilter').value;
    
    localStorage.setItem('pigstyleStreamingService', service);
    localStorage.setItem('pigstyleStreamingGenre', genre);
    
    console.log('Saved selections:', { service, genre });
}

// Main function to start playing based on current selections
function startPlaying() {
    const service = currentStreamingService;
    const genreId = document.getElementById('genreFilter').value;
    const genreName = genreId ? (genreMap[genreId] || 'Selected Genre') : 'All Genres';
    
    console.log(`Starting playback - Service: ${service}, Genre: ${genreName}`);
    
    // Save selections
    saveSelections();
    
    if (service === 'youtube') {
        startYouTubePlayback(genreId);
    } else if (service === 'spotify') {
        startSpotifyPlayback(genreId, genreName);
    }
}

// Start YouTube playback
function startYouTubePlayback(genreId) {
    console.log('Starting YouTube playback for genre:', genreId || 'All');
    
    // Stop any Spotify visualizer
    stopSpotifyVisualizer();
    
    if (youtubePlayer) {
        youtubePlayer.destroy();
        youtubePlayer = null;
    }
    
    document.getElementById('loading').style.display = 'none';
    document.getElementById('playerContent').style.display = 'block';
    
    document.getElementById('youtubeContainer').style.display = 'block';
    document.getElementById('spotifyContainer').style.display = 'none';
    document.getElementById('youtubeControls').style.display = 'flex';
    document.getElementById('visualizerControls').style.display = 'none';
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
                <p>Try selecting a different genre or switch to Spotify.</p>
            </div>
        `;
    }
}

// Start Spotify playback
function startSpotifyPlayback(genreId, genreName) {
    console.log('Starting Spotify playback for genre:', genreName);
    
    // Stop any YouTube player
    if (youtubePlayer) {
        youtubePlayer.destroy();
        youtubePlayer = null;
    }
    
    document.getElementById('loading').style.display = 'none';
    document.getElementById('playerContent').style.display = 'block';
    
    document.getElementById('spotifyContainer').style.display = 'block';
    document.getElementById('youtubeContainer').style.display = 'none';
    document.getElementById('youtubeControls').style.display = 'none';
    document.getElementById('visualizerControls').style.display = 'flex';
    document.getElementById('controlsRow').style.display = 'flex';
    
    // Fetch stored Spotify playlists from database
    fetchAndDisplayStoredPlaylists(genreName);
}

// Fetch stored Spotify playlists from database
async function fetchAndDisplayStoredPlaylists(genreName) {
    try {
        console.log('Fetching stored Spotify playlists from database...');
        
        // Build URL with genre filter if applicable
        let url = 'https://arjanshaw.pythonanywhere.com/spotify/stored-playlists';
        if (genreName !== 'All Genres') {
            url += `?genre=${encodeURIComponent(genreName)}`;
        }
        
        const response = await fetch(url);
        
        if (!response.ok) {
            throw new Error(`API error: ${response.status} ${response.statusText}`);
        }
        
        const data = await response.json();
        
        if (data.status === 'success') {
            spotifyPlaylists = data.playlists;
            console.log(`Fetched ${spotifyPlaylists.length} stored Spotify playlists`);
            
            // NEW LOGIC: Auto-select and play the matching playlist
            if (spotifyPlaylists.length > 0) {
                let matchingPlaylist = null;
                
                // For "All Genres", play the "PigStyle: All Genres" playlist
                if (genreName === 'All Genres') {
                    matchingPlaylist = spotifyPlaylists.find(p => p.name === 'PigStyle: All Genres');
                    if (!matchingPlaylist && spotifyPlaylists.length > 0) {
                        matchingPlaylist = spotifyPlaylists[0]; // Fallback to first playlist
                    }
                } else {
                    // For specific genre, find playlist with matching genre name
                    // Match format: "PigStyle: {Genre}" or exact genre name match
                    matchingPlaylist = spotifyPlaylists.find(p => 
                        p.genre === genreName || 
                        p.name === `PigStyle: ${genreName}` ||
                        p.name.includes(genreName)
                    );
                    
                    // If no exact match, find any playlist that contains the genre name
                    if (!matchingPlaylist) {
                        matchingPlaylist = spotifyPlaylists.find(p => 
                            p.name.toLowerCase().includes(genreName.toLowerCase())
                        );
                    }
                    
                    // Fallback to first playlist if still no match
                    if (!matchingPlaylist && spotifyPlaylists.length > 0) {
                        matchingPlaylist = spotifyPlaylists[0];
                    }
                }
                
                if (matchingPlaylist) {
                    selectAndPlayStoredPlaylist(matchingPlaylist);
                    return;
                }
            }
            
            // If no matching playlist found, show selection UI
            displayStoredPlaylists(spotifyPlaylists, genreName);
        } else {
            throw new Error(data.error || 'Failed to fetch stored playlists');
        }
        
    } catch (error) {
        console.error('Error fetching stored playlists:', error);
        displayStoredPlaylistsError(error.message, genreName);
    }
}

// NEW FUNCTION: Select and play a stored playlist
async function selectAndPlayStoredPlaylist(playlist) {
    console.log(`Auto-selecting playlist: ${playlist.name} (${playlist.id})`);
    
    currentSpotifyPlaylistId = playlist.id;
    
    // Clear any existing visualizer state
    stopSpotifyVisualizer();
    spotifyPlaylistTracks = [];
    spotifyVisualizerCumulativeTimes = [];
    spotifyVisualizerCurrentTrackIndex = 0;
    spotifyVisualizerCurrentTime = 0;
    spotifyVisualizerPaused = false;
    spotifyVisualizerMuted = false;
    
    // Fetch track details for visualizer
    const tracksLoaded = await fetchPlaylistTracksForVisualizer(playlist.id, playlist.name, playlist.genre);
    
    if (tracksLoaded) {
        // Show visualizer UI
        displaySpotifyVisualizer(playlist);
        
        // Start visualizer after 5 seconds
        setTimeout(() => {
            if (!spotifyVisualizerPaused) {
                startSpotifyVisualizer();
            }
        }, 5000);
    } else {
        // Fallback to embed if track fetch fails
        displayStoredPlaylistPlayer(playlist.embed_url, playlist.name, playlist.genre);
    }
}

// Fetch playlist tracks for visualizer
async function fetchPlaylistTracksForVisualizer(playlistId, playlistName, playlistGenre) {
    try {
        console.log(`Fetching tracks for playlist: ${playlistId}`);
        
        const response = await fetch(`https://arjanshaw.pythonanywhere.com/spotify/playlist-tracks/${playlistId}`);
        
        if (!response.ok) {
            throw new Error(`Failed to fetch playlist tracks: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.status === 'success') {
            spotifyPlaylistTracks = data.tracks;
            console.log(`Fetched ${spotifyPlaylistTracks.length} tracks for visualizer`);
            
            // Calculate cumulative times for track switching
            calculateCumulativeTimes();
            
            return true;
        } else {
            throw new Error(data.error || 'Failed to fetch tracks');
        }
        
    } catch (error) {
        console.error('Error fetching playlist tracks:', error);
        return false;
    }
}

// Calculate cumulative times for track switching
function calculateCumulativeTimes() {
    spotifyVisualizerCumulativeTimes = [];
    let cumulativeTime = 0;
    
    for (let i = 0; i < spotifyPlaylistTracks.length; i++) {
        spotifyVisualizerCumulativeTimes[i] = cumulativeTime;
        cumulativeTime += spotifyPlaylistTracks[i].duration_ms || 0;
    }
    
    console.log(`Calculated cumulative times for ${spotifyPlaylistTracks.length} tracks`);
}

// Display Spotify visualizer UI
function displaySpotifyVisualizer(playlist) {
    const spotifyContainer = document.getElementById('spotifyContainer');
    
    // Check if we have tracks for the visualizer
    if (spotifyPlaylistTracks.length === 0) {
        // Fallback to embed if no tracks
        displayStoredPlaylistPlayer(playlist.embed_url, playlist.name, playlist.genre);
        return;
    }
    
    spotifyContainer.innerHTML = `
        <div style="width: 100%; height: 100%;">
            <!-- Countdown timer before visualizer starts -->
            <div id="visualizerCountdown" style="text-align: center; padding: 20px; color: #1DB954; font-size: 24px; font-weight: bold; background: rgba(0, 0, 0, 0.7); border-radius: 10px; margin: 20px 0;">
                ⏱️ Visualizer starting in <span id="countdownValue">5</span> seconds...
                <div style="font-size: 16px; margin-top: 10px; color: rgba(255, 255, 255, 0.8);">
                    Press play on the Spotify player below to start audio
                </div>
            </div>
            
            <!-- Spotify embed player (shown during countdown) -->
            <div id="spotifyEmbedDuringCountdown" style="margin-bottom: 20px;">
                <iframe src="${playlist.embed_url}"
                        width="100%" 
                        height="380" 
                        frameborder="0" 
                        allowfullscreen="" 
                        allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture" 
                        loading="lazy"
                        style="border-radius: 12px;">
                </iframe>
            </div>
            
            <!-- Visualizer content (hidden initially) -->
            <div id="visualizerContent" style="display: none;">
                <div class="album-art-container">
                    <img id="albumArtImage" src="" alt="Album Art" 
                         style="width: 300px; height: 300px; border-radius: 10px; box-shadow: 0 10px 30px rgba(0,0,0,0.5);">
                    <div class="album-art-overlay">
                        <div class="track-info-large">
                            <div id="visualizerTrackTitle" class="track-title-large">Loading track...</div>
                            <div id="visualizerTrackArtist" class="track-artist-large">Loading artist...</div>
                            <div id="visualizerTrackAlbum" class="track-album-large">Loading album...</div>
                        </div>
                        <div class="track-progress">
                            <div class="progress-bar">
                                <div id="trackProgressBar" class="progress-fill" style="width: 0%;"></div>
                            </div>
                            <div class="time-display">
                                <span id="currentTime">0:00</span>
                                <span id="trackDuration">0:00</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Fallback to embed if visualizer fails -->
            <div id="spotifyEmbedFallback" style="display: none;">
                <iframe src="${playlist.embed_url}"
                        width="100%" 
                        height="380" 
                        frameborder="0" 
                        allowfullscreen="" 
                        allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture" 
                        loading="lazy"
                        style="border-radius: 12px;">
                </iframe>
            </div>
        </div>
    `;
    
    // Start countdown
    startVisualizerCountdown();
    
    // Update track info with first track
    if (spotifyPlaylistTracks.length > 0) {
        const firstTrack = spotifyPlaylistTracks[0];
        updateTrackInfoForSpotify(firstTrack, playlist);
    }
}

// Update track info for Spotify tracks
function updateTrackInfoForSpotify(track, playlist) {
    document.getElementById('trackTitle').textContent = track.name || 'Unknown Track';
    document.getElementById('trackArtist').textContent = track.artists ? track.artists.join(', ') : 'Unknown Artist';
    
    // Try to find matching record in database for price and voting
    findMatchingRecord(track.name, track.artists ? track.artists[0] : 'Unknown', playlist.genre);
}

// Find matching record in database for voting and price
async function findMatchingRecord(trackName, artistName, genreName) {
    try {
        // Search for record matching track/artist
        const response = await fetch(`https://arjanshaw.pythonanywhere.com/records?limit=1000`);
        const data = await response.json();
        
        if (data && data.records) {
            // Simple matching logic - could be improved
            const matchingRecord = data.records.find(record => 
                (record.title && record.title.toLowerCase().includes(trackName.toLowerCase())) ||
                (record.artist && record.artist.toLowerCase().includes(artistName.toLowerCase()))
            );
            
            if (matchingRecord) {
                currentRecordId = matchingRecord.id;
                // Update price display
                const priceElement = document.getElementById('trackPrice');
                if (priceElement && matchingRecord.store_price) {
                    priceElement.textContent = `$${parseFloat(matchingRecord.store_price).toFixed(2)}`;
                }
                votingSystem.updateVoteDisplay(matchingRecord);
                return matchingRecord;
            }
        }
        
        // If no match found, try to get a record from this genre
        const genreRecord = data.records.find(record => 
            record.genre_name === genreName || record.genre_name === 'All Genres'
        );
        
        if (genreRecord) {
            currentRecordId = genreRecord.id;
            // Update price display
            const priceElement = document.getElementById('trackPrice');
            if (priceElement && genreRecord.store_price) {
                priceElement.textContent = `$${parseFloat(genreRecord.store_price).toFixed(2)}`;
            }
            votingSystem.updateVoteDisplay(genreRecord);
            return genreRecord;
        }
        
        // Default fallback
        currentRecordId = null;
        const priceElement = document.getElementById('trackPrice');
        if (priceElement) {
            priceElement.textContent = '$0.00';
        }
        votingSystem.updateVoteDisplay({ up_votes: 0, down_votes: 0, kill_votes: 0 });
        return null;
        
    } catch (error) {
        console.error('Error finding matching record:', error);
        currentRecordId = null;
        const priceElement = document.getElementById('trackPrice');
        if (priceElement) {
            priceElement.textContent = '$0.00';
        }
        return null;
    }
}

// Handle stop button click
function handleStopVisualizer() {
    spotifyVisualizerPaused = !spotifyVisualizerPaused;
    
    const stopBtn = document.getElementById('stopBtn');
    if (stopBtn) {
        if (spotifyVisualizerPaused) {
            stopSpotifyVisualizer();
            stopBtn.innerHTML = '<i class="fas fa-play"></i>';
            stopBtn.title = "Play";
        } else {
            startSpotifyVisualizer();
            stopBtn.innerHTML = '<i class="fas fa-stop"></i>';
            stopBtn.title = "Stop";
        }
    }
}

// Handle mute button click
function handleMuteVisualizer() {
    spotifyVisualizerMuted = !spotifyVisualizerMuted;
    
    const muteBtn = document.getElementById('muteBtn');
    if (muteBtn) {
        if (spotifyVisualizerMuted) {
            muteBtn.innerHTML = '<i class="fas fa-volume-up"></i>';
            muteBtn.title = "Unmute";
            muteBtn.classList.add('muted');
        } else {
            muteBtn.innerHTML = '<i class="fas fa-volume-mute"></i>';
            muteBtn.title = "Mute";
            muteBtn.classList.remove('muted');
        }
    }
    
    console.log('Visualizer muted:', spotifyVisualizerMuted);
}

// Start visualizer countdown
function startVisualizerCountdown() {
    let countdown = 5;
    const countdownElement = document.getElementById('countdownValue');
    const countdownInterval = setInterval(() => {
        if (spotifyVisualizerPaused) {
            clearInterval(countdownInterval);
            return;
        }
        
        countdown--;
        countdownElement.textContent = countdown;
        
        if (countdown <= 0) {
            clearInterval(countdownInterval);
            // Hide countdown and Spotify embed
            document.getElementById('visualizerCountdown').style.display = 'none';
            document.getElementById('spotifyEmbedDuringCountdown').style.display = 'none';
            // Show visualizer
            document.getElementById('visualizerContent').style.display = 'block';
        }
    }, 1000);
}

// Start Spotify visualizer
function startSpotifyVisualizer() {
    if (spotifyVisualizerActive) {
        return;
    }
    
    if (spotifyPlaylistTracks.length === 0) {
        console.error('No tracks available for visualizer');
        return;
    }
    
    spotifyVisualizerActive = true;
    spotifyVisualizerStartTime = Date.now();
    spotifyVisualizerCurrentTrackIndex = 0;
    spotifyVisualizerCurrentTime = 0;
    
    // Update display for first track
    updateVisualizerDisplay();
    
    // Start the timer
    spotifyVisualizerTimer = setInterval(updateVisualizerTimer, 1000);
    
    console.log('Spotify visualizer started');
}

// Update visualizer timer
function updateVisualizerTimer() {
    if (!spotifyVisualizerActive || spotifyVisualizerPaused || spotifyPlaylistTracks.length === 0) {
        return;
    }
    
    const now = Date.now();
    const elapsed = now - spotifyVisualizerStartTime;
    spotifyVisualizerCurrentTime = elapsed;
    
    // Check if we need to switch to next track
    const currentTrack = spotifyPlaylistTracks[spotifyVisualizerCurrentTrackIndex];
    const currentTrackDuration = currentTrack.duration_ms || 30000; // Default 30 seconds if no duration
    
    if (elapsed >= spotifyVisualizerCumulativeTimes[spotifyVisualizerCurrentTrackIndex] + currentTrackDuration) {
        // Move to next track
        spotifyVisualizerCurrentTrackIndex++;
        
        if (spotifyVisualizerCurrentTrackIndex >= spotifyPlaylistTracks.length) {
            // Loop back to beginning
            spotifyVisualizerCurrentTrackIndex = 0;
            spotifyVisualizerStartTime = now;
            spotifyVisualizerCurrentTime = 0;
        }
        
        updateVisualizerDisplay();
    }
    
    // Update progress bar
    updateProgressBar();
    
    // Update time display
    updateTimeDisplay();
}

// Update visualizer display for current track
function updateVisualizerDisplay() {
    if (spotifyPlaylistTracks.length === 0 || spotifyVisualizerCurrentTrackIndex >= spotifyPlaylistTracks.length) {
        return;
    }
    
    const track = spotifyPlaylistTracks[spotifyVisualizerCurrentTrackIndex];
    
    // Update album art
    const albumArtImg = document.getElementById('albumArtImage');
    if (track.album_art_url) {
        albumArtImg.src = track.album_art_url;
        albumArtImg.style.display = 'block';
    } else {
        albumArtImg.style.display = 'none';
    }
    
    // Update track info
    document.getElementById('visualizerTrackTitle').textContent = track.name || 'Unknown Track';
    document.getElementById('visualizerTrackArtist').textContent = track.artists ? track.artists.join(', ') : 'Unknown Artist';
    document.getElementById('visualizerTrackAlbum').textContent = track.album_name || 'Unknown Album';
    
    // Update main track display and find matching record for voting and price
    const currentPlaylist = spotifyPlaylists.find(p => p.id === currentSpotifyPlaylistId);
    updateTrackInfoForSpotify(track, currentPlaylist);
}

// Update progress bar
function updateProgressBar() {
    if (spotifyPlaylistTracks.length === 0) {
        return;
    }
    
    const track = spotifyPlaylistTracks[spotifyVisualizerCurrentTrackIndex];
    const trackDuration = track.duration_ms || 30000;
    const trackStartTime = spotifyVisualizerCumulativeTimes[spotifyVisualizerCurrentTrackIndex];
    const elapsedInTrack = spotifyVisualizerCurrentTime - trackStartTime;
    const progressPercent = Math.min(100, (elapsedInTrack / trackDuration) * 100);
    
    const progressBar = document.getElementById('trackProgressBar');
    if (progressBar) {
        progressBar.style.width = `${progressPercent}%`;
    }
}

// Update time display
function updateTimeDisplay() {
    if (spotifyPlaylistTracks.length === 0) {
        return;
    }
    
    const track = spotifyPlaylistTracks[spotifyVisualizerCurrentTrackIndex];
    const trackDuration = track.duration_ms || 30000;
    const trackStartTime = spotifyVisualizerCumulativeTimes[spotifyVisualizerCurrentTrackIndex];
    const elapsedInTrack = Math.max(0, spotifyVisualizerCurrentTime - trackStartTime);
    
    // Format current time
    const currentSeconds = Math.floor(elapsedInTrack / 1000);
    const currentMinutes = Math.floor(currentSeconds / 60);
    const currentSecs = currentSeconds % 60;
    
    // Format total duration
    const totalSeconds = Math.floor(trackDuration / 1000);
    const totalMinutes = Math.floor(totalSeconds / 60);
    const totalSecs = totalSeconds % 60;
    
    const currentTimeElement = document.getElementById('currentTime');
    const durationElement = document.getElementById('trackDuration');
    
    if (currentTimeElement) {
        currentTimeElement.textContent = `${currentMinutes}:${currentSecs.toString().padStart(2, '0')}`;
    }
    
    if (durationElement) {
        durationElement.textContent = `${totalMinutes}:${totalSecs.toString().padStart(2, '0')}`;
    }
}

// Stop Spotify visualizer
function stopSpotifyVisualizer() {
    spotifyVisualizerActive = false;
    if (spotifyVisualizerTimer) {
        clearInterval(spotifyVisualizerTimer);
        spotifyVisualizerTimer = null;
    }
    console.log('Spotify visualizer stopped');
}

// Display stored playlist player with embed
function displayStoredPlaylistPlayer(embedUrl, playlistName, playlistGenre) {
    const spotifyContainer = document.getElementById('spotifyContainer');
    
    spotifyContainer.innerHTML = `
        <div style="width: 100%; height: 100%;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; padding: 0 10px;">
                <h4 style="margin: 0; color: white; font-size: 18px;">
                    🎵 Now Playing: <span style="color: #1DB954;">${playlistName}</span>
                </h4>
                <button onclick="fetchAndDisplayStoredPlaylists('${playlistGenre || ''}')"
                        style="padding: 6px 12px; background: rgba(255, 255, 255, 0.1); color: white; border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 4px; cursor: pointer; font-size: 13px;">
                    Back to Playlists
                </button>
            </div>
            
            <iframe src="${embedUrl}"
                    width="100%" 
                    height="380" 
                    frameborder="0" 
                    allowfullscreen="" 
                    allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture" 
                    loading="lazy"
                    style="border-radius: 12px;">
            </iframe>
            
            <div style="text-align: center; margin-top: 15px; padding: 10px; background: rgba(29, 185, 84, 0.1); border-radius: 6px;">
                <p style="margin: 0; color: #1DB954; font-size: 14px;">
                    ♫ Playing from Spotify • Use Spotify controls above to play/pause
                </p>
            </div>
        </div>
    `;
    
    // Update track info
    document.getElementById('trackTitle').textContent = playlistName;
    document.getElementById('trackArtist').textContent = `Genre: ${playlistGenre || 'Various'}`;
    const priceElement = document.getElementById('trackPrice');
    if (priceElement) {
        priceElement.textContent = '$0.00';
    }
    
    // Try to find a matching record for voting
    findMatchingRecord(playlistName, playlistGenre, playlistGenre);
}

// Display stored playlists in the UI
function displayStoredPlaylists(playlists, genreName) {
    const spotifyContainer = document.getElementById('spotifyContainer');
    
    if (playlists.length === 0) {
        spotifyContainer.innerHTML = `
            <div style="padding: 40px; text-align: center; color: white;">
                <h3>🎵 No Stored Spotify Playlists</h3>
                <p>No PigStyle playlists are currently available in the database.</p>
                <p>You can create playlists by running the Spotify update tool.</p>
                <div style="margin-top: 20px;">
                    <button onclick="switchToYouTube()" style="padding: 10px 20px; background: #FF0000; color: white; border: none; border-radius: 5px; margin: 5px;">
                        Switch to YouTube
                    </button>
                </div>
            </div>
        `;
        
        // Update track info
        document.getElementById('trackTitle').textContent = 'No Playlists Available';
        document.getElementById('trackArtist').textContent = 'Create playlists first';
        const priceElement = document.getElementById('trackPrice');
        if (priceElement) {
            priceElement.textContent = '$0.00';
        }
        return;
    }
    
    // Create playlist selection UI
    let playlistHTML = `
        <div style="padding: 20px; color: white;">
            <h3 style="margin-bottom: 20px; text-align: center;">🎵 PigStyle Spotify Playlists</h3>
            <p style="text-align: center; margin-bottom: 20px; opacity: 0.8;">
                ${genreName === 'All Genres' ? 'All Genres' : `Genre: ${genreName}`} • ${playlists.length} playlists
            </p>
            
            <div style="
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
                gap: 15px;
                max-height: 400px;
                overflow-y: auto;
                padding: 10px;
            ">
    `;
    
    playlists.forEach((playlist, index) => {
        const isSelected = currentSpotifyPlaylistId === playlist.id;
        playlistHTML += `
            <div style="
                background: ${isSelected ? 'rgba(29, 185, 84, 0.2)' : 'rgba(255, 255, 255, 0.1)'};
                border: 1px solid ${isSelected ? '#1DB954' : 'rgba(255, 255, 255, 0.2)'};
                border-radius: 8px;
                padding: 15px;
                cursor: pointer;
                transition: all 0.3s ease;
                ${isSelected ? 'box-shadow: 0 0 10px rgba(29, 185, 84, 0.5);' : ''}
            " 
            onclick="selectAndPlayStoredPlaylist(${JSON.stringify(playlist).replace(/"/g, '&quot;')})"
            onmouseover="this.style.transform='translateY(-2px)'; this.style.backgroundColor='${isSelected ? 'rgba(29, 185, 84, 0.3)' : 'rgba(255, 255, 255, 0.15)'}'"
            onmouseout="this.style.transform='translateY(0)'; this.style.backgroundColor='${isSelected ? 'rgba(29, 185, 84, 0.2)' : 'rgba(255, 255, 255, 0.1)'}'">
                <div style="display: flex; align-items: center; margin-bottom: 10px;">
                    <div style="
                        width: 40px;
                        height: 40px;
                        background: linear-gradient(135deg, #1DB954, #1ed760);
                        border-radius: 4px;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        margin-right: 12px;
                        font-size: 20px;
                    ">
                        ${index + 1}
                    </div>
                    <div style="flex: 1;">
                        <h4 style="margin: 0 0 5px 0; font-size: 16px; color: ${isSelected ? '#1DB954' : 'white'};">
                            ${playlist.name}
                        </h4>
                        <div style="font-size: 12px; opacity: 0.7; display: flex; align-items: center; gap: 10px;">
                            <span>${playlist.tracks} tracks</span>
                            <span>•</span>
                            <span>${playlist.genre || 'Various'}</span>
                        </div>
                    </div>
                </div>
                
                <p style="
                    font-size: 13px;
                    opacity: 0.8;
                    margin: 8px 0 0 0;
                    line-height: 1.4;
                    font-style: italic;
                    border-left: 2px solid rgba(29, 185, 84, 0.5);
                    padding-left: 10px;
                ">
                    ${playlist.description || 'PigStyle Records Collection'}
                </p>
                
                <div style="margin-top: 12px; display: flex; justify-content: space-between; align-items: center;">
                    <button onclick="event.stopPropagation(); selectAndPlayStoredPlaylist(${JSON.stringify(playlist).replace(/"/g, '&quot;')})"
                            style="
                                padding: 6px 12px;
                                background: ${isSelected ? '#1DB954' : 'rgba(29, 185, 84, 0.3)'};
                                color: white;
                                border: none;
                                border-radius: 4px;
                                cursor: pointer;
                                font-size: 13px;
                                transition: background 0.3s;
                            "
                            onmouseover="this.style.backgroundColor='#1DB954'"
                            onmouseout="this.style.backgroundColor='${isSelected ? '#1DB954' : 'rgba(29, 185, 84, 0.3)'}'">
                        ${isSelected ? '✓ Playing' : 'Play'}
                    </button>
                    
                    <a href="${playlist.url}" 
                       target="_blank"
                       onclick="event.stopPropagation();"
                       style="
                            font-size: 12px;
                            color: #1DB954;
                            text-decoration: none;
                            opacity: 0.8;
                            transition: opacity 0.3s;
                       "
                       onmouseover="this.style.opacity='1';"
                       onmouseout="this.style.opacity='0.8';">
                        Open in Spotify ↗
                    </a>
                </div>
            </div>
        `;
    });
    
    playlistHTML += `
            </div>
            
            <div style="text-align: center; margin-top: 25px; padding-top: 20px; border-top: 1px solid rgba(255, 255, 255, 0.1);">
                <p style="opacity: 0.7; font-size: 14px; margin-bottom: 15px;">
                    Showing ${playlists.length} PigStyle playlists from database
                    ${genreName !== 'All Genres' ? `(filtered by: ${genreName})` : ''}
                </p>
                <div>
                    <button onclick="fetchAndDisplayStoredPlaylists('${genreName.replace(/'/g, "\\'")}')" 
                            style="padding: 8px 16px; background: rgba(255, 255, 255, 0.1); color: white; border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 4px; cursor: pointer; margin: 0 5px;">
                        Refresh Playlists
                    </button>
                    <button onclick="switchToYouTube()" 
                            style="padding: 8px 16px; background: rgba(255, 0, 0, 0.2); color: #ff6b6b; border: 1px solid rgba(255, 0, 0, 0.3); border-radius: 4px; cursor: pointer; margin: 0 5px;">
                        Switch to YouTube
                    </button>
                </div>
            </div>
        </div>
    `;
    
    spotifyContainer.innerHTML = playlistHTML;
    
    // Update track info
    document.getElementById('trackTitle').textContent = 'PigStyle Spotify Playlists';
    document.getElementById('trackArtist').textContent = `${playlists.length} playlists available`;
    const priceElement = document.getElementById('trackPrice');
    if (priceElement) {
        priceElement.textContent = '$0.00';
    }
    
    // Reset current record ID when showing playlist selection
    currentRecordId = null;
    votingSystem.updateVoteDisplay({ up_votes: 0, down_votes: 0, kill_votes: 0 });
}

// Display stored playlists error
function displayStoredPlaylistsError(errorMessage, genreName) {
    const spotifyContainer = document.getElementById('spotifyContainer');
    
    spotifyContainer.innerHTML = `
        <div style="padding: 40px; text-align: center; color: white;">
            <h3>⚠️ Error Loading Stored Playlists</h3>
            <p>Failed to load PigStyle playlists from database.</p>
            <p style="opacity: 0.7; margin: 10px 0; font-size: 14px;">Error: ${errorMessage}</p>
            <p>Please check:</p>
            <ul style="text-align: left; display: inline-block; opacity: 0.8; margin: 15px 0;">
                <li>Database connection is working</li>
                <li>Spotify playlists have been created</li>
                <li>spotify_playlists table exists</li>
            </ul>
            <div style="margin-top: 20px;">
                <button onclick="fetchAndDisplayStoredPlaylists('${genreName.replace(/'/g, "\\'")}')" 
                        style="padding: 10px 20px; background: #1DB954; color: white; border: none; border-radius: 5px; margin: 5px;">
                    Try Again
                </button>
                <button onclick="switchToYouTube()" 
                        style="padding: 10px 20px; background: #FF0000; color: white; border: none; border-radius: 5px; margin: 5px;">
                    Switch to YouTube
                </button>
            </div>
        </div>
    `;
    
    // Update track info
    document.getElementById('trackTitle').textContent = 'Database Error';
    document.getElementById('trackArtist').textContent = 'Failed to load playlists';
    const priceElement = document.getElementById('trackPrice');
    if (priceElement) {
        priceElement.textContent = '$0.00';
    }
    
    // Reset current record ID
    currentRecordId = null;
}

// Switch to YouTube mode
function switchToYouTube() {
    // Stop Spotify visualizer if active
    stopSpotifyVisualizer();
    
    currentStreamingService = 'youtube';
    updateServiceIcons('youtube');
    startPlaying();
}

// Switch to Spotify mode
function switchToSpotify() {
    currentStreamingService = 'spotify';
    updateServiceIcons('spotify');
    startPlaying();
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
    
    // Update vote display
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

// Setup service selector and other UI
function setupUI() {
    const youtubeIcon = document.getElementById('youtubeIcon');
    const spotifyIcon = document.getElementById('spotifyIcon');
    const genreFilter = document.getElementById('genreFilter');
    
    if (youtubeIcon) {
        youtubeIcon.addEventListener('click', function() {
            currentStreamingService = 'youtube';
            updateServiceIcons('youtube');
            console.log('Service changed to: YouTube');
            startPlaying();
        });
    }
    
    if (spotifyIcon) {
        spotifyIcon.addEventListener('click', function() {
            currentStreamingService = 'spotify';
            updateServiceIcons('spotify');
            console.log('Service changed to: Spotify');
            startPlaying();
        });
    }
    
    if (genreFilter) {
        genreFilter.addEventListener('change', function() {
            console.log('Genre changed to:', this.value);
            startPlaying();
        });
    }
    
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    const stopBtn = document.getElementById('stopBtn');
    const muteBtn = document.getElementById('muteBtn');
    
    if (prevBtn) prevBtn.addEventListener('click', playPreviousTrack);
    if (nextBtn) nextBtn.addEventListener('click', playNextTrack);
    if (stopBtn) stopBtn.addEventListener('click', handleStopVisualizer);
    if (muteBtn) muteBtn.addEventListener('click', handleMuteVisualizer);
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
    const currentTrack = document.querySelector('.current-track');
    const videoContainer = document.querySelector('.video-container');
    
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
    
    // Initialize voting system
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
window.switchToYouTube = switchToYouTube;
window.switchToSpotify = switchToSpotify;
window.startPlaying = startPlaying;
window.fetchAndDisplayStoredPlaylists = fetchAndDisplayStoredPlaylists;
window.selectAndPlayStoredPlaylist = selectAndPlayStoredPlaylist;
window.handleStopVisualizer = handleStopVisualizer;
window.handleMuteVisualizer = handleMuteVisualizer;
window.scaleDown = scaleDown;
window.scaleUp = scaleUp;
window.resetScale = resetScale;