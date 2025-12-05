// streaming.js - Get genres from records, random start, no condition stars

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
    
    // Fetch Spotify playlists and display them
    fetchAndDisplaySpotifyPlaylists(genreName);
}

// Fetch Spotify playlists from API
async function fetchAndDisplaySpotifyPlaylists(genreName) {
    try {
        console.log('Fetching Spotify playlists...');
        
        const response = await fetch('https://arjanshaw.pythonanywhere.com/spotify/playlists');
        
        if (!response.ok) {
            throw new Error(`API error: ${response.status} ${response.statusText}`);
        }
        
        const data = await response.json();
        
        if (data.status === 'success') {
            spotifyPlaylists = data.playlists;
            console.log(`Fetched ${spotifyPlaylists.length} Spotify playlists`);
            
            // Display playlists in UI
            displaySpotifyPlaylists(spotifyPlaylists, genreName);
        } else {
            throw new Error(data.error || 'Failed to fetch playlists');
        }
        
    } catch (error) {
        console.error('Error fetching Spotify playlists:', error);
        displaySpotifyError(error.message);
    }
}

// Display Spotify playlists in the UI
function displaySpotifyPlaylists(playlists, genreName) {
    const spotifyContainer = document.getElementById('spotifyContainer');
    
    if (playlists.length === 0) {
        spotifyContainer.innerHTML = `
            <div style="padding: 40px; text-align: center; color: white;">
                <h3>🎵 No Spotify Playlists Found</h3>
                <p>No playlists are currently available on Spotify.</p>
                <p>You can create playlists using the admin tools.</p>
                <div style="margin-top: 20px;">
                    <button onclick="switchToYouTube()" style="padding: 10px 20px; background: #FF0000; color: white; border: none; border-radius: 5px; margin: 5px;">
                        Switch to YouTube
                    </button>
                </div>
            </div>
        `;
        return;
    }
    
    // Create playlist selection UI
    let playlistHTML = `
        <div style="padding: 20px; color: white;">
            <h3 style="margin-bottom: 20px; text-align: center;">🎵 Available Spotify Playlists</h3>
            <p style="text-align: center; margin-bottom: 20px; opacity: 0.8;">Select a playlist to play:</p>
            
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
            onclick="selectSpotifyPlaylist('${playlist.id}', '${playlist.name.replace(/'/g, "\\'")}')"
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
                            <span>${playlist.public ? 'Public' : 'Private'}</span>
                        </div>
                    </div>
                </div>
                
                ${playlist.description ? `
                <p style="
                    font-size: 13px;
                    opacity: 0.8;
                    margin: 8px 0 0 0;
                    line-height: 1.4;
                    font-style: italic;
                    border-left: 2px solid rgba(29, 185, 84, 0.5);
                    padding-left: 10px;
                ">
                    "${playlist.description}"
                </p>
                ` : ''}
                
                <div style="margin-top: 12px; display: flex; justify-content: space-between; align-items: center;">
                    <button onclick="event.stopPropagation(); selectSpotifyPlaylist('${playlist.id}', '${playlist.name.replace(/'/g, "\\'")}')"
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
                    Showing ${playlists.length} playlists from Spotify API
                </p>
                <div>
                    <button onclick="fetchAndDisplaySpotifyPlaylists('${genreName.replace(/'/g, "\\'")}')" 
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
    document.getElementById('trackTitle').textContent = 'Select a Spotify Playlist';
    document.getElementById('trackArtist').textContent = `${spotifyPlaylists.length} playlists available`;
    document.getElementById('trackPrice').textContent = 'Stream Now';
}

// Display Spotify error
function displaySpotifyError(errorMessage) {
    const spotifyContainer = document.getElementById('spotifyContainer');
    
    spotifyContainer.innerHTML = `
        <div style="padding: 40px; text-align: center; color: white;">
            <h3>⚠️ Error Loading Spotify Playlists</h3>
            <p>Failed to load playlists from Spotify API.</p>
            <p style="opacity: 0.7; margin: 10px 0; font-size: 14px;">Error: ${errorMessage}</p>
            <p>Please check:</p>
            <ul style="text-align: left; display: inline-block; opacity: 0.8; margin: 15px 0;">
                <li>Spotify API credentials are set</li>
                <li>Server can access Spotify API</li>
                <li>Network connection is working</li>
            </ul>
            <div style="margin-top: 20px;">
                <button onclick="fetchAndDisplaySpotifyPlaylists('All Genres')" 
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
    document.getElementById('trackTitle').textContent = 'Spotify API Error';
    document.getElementById('trackArtist').textContent = 'Failed to load playlists';
    document.getElementById('trackPrice').textContent = 'Please Try Again';
}

// Select a Spotify playlist
function selectSpotifyPlaylist(playlistId, playlistName) {
    console.log(`Selected Spotify playlist: ${playlistName} (${playlistId})`);
    
    currentSpotifyPlaylistId = playlistId;
    
    // Get embed URL from API
    fetch(`https://arjanshaw.pythonanywhere.com/spotify/playlist/${playlistId}/embed`)
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                displaySpotifyPlayer(data.embed_url, playlistName);
            } else {
                // Fallback to direct embed URL
                const embedUrl = `https://open.spotify.com/embed/playlist/${playlistId}?utm_source=generator&theme=0`;
                displaySpotifyPlayer(embedUrl, playlistName);
            }
        })
        .catch(error => {
            console.error('Error getting embed URL:', error);
            // Fallback to direct embed URL
            const embedUrl = `https://open.spotify.com/embed/playlist/${playlistId}?utm_source=generator&theme=0`;
            displaySpotifyPlayer(embedUrl, playlistName);
        });
}

// Display Spotify player with embed
function displaySpotifyPlayer(embedUrl, playlistName) {
    const spotifyContainer = document.getElementById('spotifyContainer');
    
    spotifyContainer.innerHTML = `
        <div style="width: 100%; height: 100%;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; padding: 0 10px;">
                <h4 style="margin: 0; color: white; font-size: 18px;">
                    🎵 Now Playing: <span style="color: #1DB954;">${playlistName}</span>
                </h4>
                <button onclick="fetchAndDisplaySpotifyPlaylists('')"
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
    document.getElementById('trackArtist').textContent = 'Spotify Playlist';
    document.getElementById('trackPrice').textContent = 'Streaming Now';
}

// Switch to YouTube mode
function switchToYouTube() {
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
window.fetchAndDisplaySpotifyPlaylists = fetchAndDisplaySpotifyPlaylists;
window.selectSpotifyPlaylist = selectSpotifyPlaylist;