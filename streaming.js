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

// Main function to start playing based on current selections
function startPlaying() {
    const service = currentStreamingService;
    const genreId = document.getElementById('genreFilter').value;
    const genreName = genreId ? (genreMap[genreId] || 'Selected Genre') : 'All Genres';
    
    console.log(`Starting playback - Service: ${service}, Genre: ${genreName}`);
    
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
    document.getElementById('spotifyControls').style.display = 'none';
    
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
    document.getElementById('spotifyControls').style.display = 'flex';
    document.getElementById('youtubeControls').style.display = 'none';
    
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
                // For "All Genres", play the "PigStyle: All Genres" playlist
                if (genreName === 'All Genres') {
                    const allGenresPlaylist = spotifyPlaylists.find(p => p.name === 'PigStyle: All Genres');
                    if (allGenresPlaylist) {
                        selectAndPlayStoredPlaylist(allGenresPlaylist);
                        return;
                    }
                } else {
                    // For specific genre, find playlist with matching genre name
                    // Match format: "PigStyle: {Genre}" or exact genre name match
                    const matchingPlaylist = spotifyPlaylists.find(p => 
                        p.genre === genreName || 
                        p.name === `PigStyle: ${genreName}` ||
                        p.name.includes(genreName)
                    );
                    
                    if (matchingPlaylist) {
                        selectAndPlayStoredPlaylist(matchingPlaylist);
                        return;
                    }
                }
                
                // If no exact match found, show selection UI
                displayStoredPlaylists(spotifyPlaylists, genreName);
            } else {
                displayStoredPlaylistsError('No playlists found in database', genreName);
            }
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
    
    // Fetch track details for visualizer
    await fetchPlaylistTracksForVisualizer(playlist.id, playlist.name, playlist.genre);
    
    // Show visualizer UI instead of embed
    displaySpotifyVisualizer(playlist);
    
    // Start visualizer after 5 seconds
    setTimeout(() => {
        startSpotifyVisualizer();
    }, 5000);
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
        // Fallback to showing embed if track fetch fails
        displayStoredPlaylistPlayer(playlistId, playlistName, playlistGenre);
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
                
                <div class="playlist-info">
                    <div class="current-track-info">
                        <h5>Now Playing</h5>
                        <div id="nowPlayingTrack">Track 1 of ${spotifyPlaylistTracks.length}</div>
                        <div id="nowPlayingTime">Total playlist time: ${formatPlaylistDuration()}</div>
                    </div>
                    <div class="upcoming-tracks">
                        <h5>Upcoming Tracks</h5>
                        <div id="upcomingTracksList" style="max-height: 150px; overflow-y: auto;">
                            ${getUpcomingTracksHTML()}
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
    
    // Update track info with price instead of track count
    document.getElementById('trackTitle').textContent = playlist.name;
    document.getElementById('trackArtist').textContent = `Genre: ${playlist.genre || 'Various'}`;
    // Replace track count with price placeholder - you'll need to fetch actual price data
    document.getElementById('trackPrice').textContent = 'Stream Now';
}

// Start visualizer countdown
function startVisualizerCountdown() {
    let countdown = 5;
    const countdownElement = document.getElementById('countdownValue');
    const countdownInterval = setInterval(() => {
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
    if (!spotifyVisualizerActive || spotifyPlaylistTracks.length === 0) {
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
    
    // Update now playing info
    document.getElementById('nowPlayingTrack').textContent = `Track ${spotifyVisualizerCurrentTrackIndex + 1} of ${spotifyPlaylistTracks.length}`;
    
    // Update upcoming tracks
    updateUpcomingTracks();
    
    // Also update main track display
    document.getElementById('trackTitle').textContent = track.name || 'Unknown Track';
    document.getElementById('trackArtist').textContent = track.artists ? track.artists.join(', ') : 'Unknown Artist';
    document.getElementById('trackPrice').textContent = getTrackPrice(track);
    
    // Update vote display
    const trackId = `${track.artists ? track.artists[0] : 'Unknown'} - ${track.name || 'Unknown'}`;
    votingSystem.updateVoteDisplay(trackId);
}

// Get track price - you'll need to implement this based on your database
function getTrackPrice(track) {
    // This is a placeholder - you need to fetch actual price from your database
    // based on track name and artist
    return '$24.99'; // Default placeholder price
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

// Update upcoming tracks list
function updateUpcomingTracks() {
    const upcomingTracksList = document.getElementById('upcomingTracksList');
    if (upcomingTracksList) {
        upcomingTracksList.innerHTML = getUpcomingTracksHTML();
    }
}

// Get HTML for upcoming tracks
function getUpcomingTracksHTML() {
    let html = '';
    const startIndex = spotifyVisualizerCurrentTrackIndex + 1;
    const endIndex = Math.min(startIndex + 5, spotifyPlaylistTracks.length);
    
    for (let i = startIndex; i < endIndex; i++) {
        const track = spotifyPlaylistTracks[i];
        html += `
            <div class="upcoming-track-item" style="padding: 5px 0; border-bottom: 1px solid rgba(255,255,255,0.1);">
                <div style="font-weight: bold; font-size: 14px;">${track.name || 'Unknown Track'}</div>
                <div style="font-size: 12px; opacity: 0.8;">${track.artists ? track.artists.join(', ') : 'Unknown Artist'}</div>
            </div>
        `;
    }
    
    if (html === '') {
        html = '<div style="padding: 10px; text-align: center; opacity: 0.7;">End of playlist</div>';
    }
    
    return html;
}

// Format playlist duration
function formatPlaylistDuration() {
    if (spotifyPlaylistTracks.length === 0) {
        return '0:00';
    }
    
    const totalMs = spotifyVisualizerCumulativeTimes[spotifyPlaylistTracks.length - 1] + 
                   (spotifyPlaylistTracks[spotifyPlaylistTracks.length - 1].duration_ms || 0);
    
    const totalMinutes = Math.floor(totalMs / 60000);
    const totalHours = Math.floor(totalMinutes / 60);
    
    if (totalHours > 0) {
        return `${totalHours}h ${totalMinutes % 60}m`;
    } else {
        return `${totalMinutes}m`;
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
    document.getElementById('trackPrice').textContent = 'Stream Now';
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
        document.getElementById('trackPrice').textContent = 'Setup Required';
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
    document.getElementById('trackPrice').textContent = 'Select a playlist';
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
    document.getElementById('trackPrice').textContent = 'Please Try Again';
}

// Switch to YouTube mode
function switchToYouTube() {
    // Stop Spotify visualizer if active
    stopSpotifyVisualizer();
    
    document.getElementById('streamingService').value = 'youtube';
    currentStreamingService = 'youtube';
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
    const serviceSelector = document.getElementById('streamingService');
    const genreFilter = document.getElementById('genreFilter');
    
    if (serviceSelector) {
        serviceSelector.addEventListener('change', function(e) {
            currentStreamingService = e.target.value;
            console.log('Service changed to:', currentStreamingService);
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
    
    // Load records and start playing
    setTimeout(loadRecordsFromAPI, 500);
});

// Make functions available globally
window.playPreviousTrack = playPreviousTrack;
window.playNextTrack = playNextTrack;
window.switchToYouTube = switchToYouTube;
window.startPlaying = startPlaying;
window.fetchAndDisplayStoredPlaylists = fetchAndDisplayStoredPlaylists;
window.selectAndPlayStoredPlaylist = selectAndPlayStoredPlaylist;