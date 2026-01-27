// streaming.js - Get genres from records, true shuffle, YouTube only

console.log('streaming.js loaded!');

// ========== GLOBAL VARIABLES ==========
let allRecords = [];
let filteredRecords = [];
let shuffledIndices = [];      // Array of shuffled indices
let shuffleCurrentIndex = 0;   // Current position in shuffled playlist
let youtubePlayer = null;
let youtubeAPILoaded = false;
let genreMap = {};

// ========== YOUTUBE PLAYER FUNCTIONS ==========

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

// ========== SHUFFLE FUNCTIONS ==========

// Generate a shuffled playlist (Fisher-Yates algorithm)
function generateShuffledPlaylist(records) {
    // Create array of indices [0, 1, 2, ..., n-1]
    shuffledIndices = Array.from({ length: records.length }, (_, i) => i);
    
    // Shuffle the indices using Fisher-Yates algorithm
    for (let i = shuffledIndices.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [shuffledIndices[i], shuffledIndices[j]] = [shuffledIndices[j], shuffledIndices[i]];
    }
    
    shuffleCurrentIndex = 0;
    console.log(`Generated shuffled playlist of ${shuffledIndices.length} tracks`);
    console.log('Shuffled indices:', shuffledIndices);
}

// Get the actual array index for current track (using shuffled indices)
function getCurrentShuffledIndex() {
    if (shuffledIndices.length === 0) return 0;
    return shuffledIndices[shuffleCurrentIndex];
}

// ========== CORE FUNCTIONS ==========

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
        // GENERATE SHUFFLED PLAYLIST (TRUE SHUFFLE)
        generateShuffledPlaylist(filteredRecords);
        
        // Start at first shuffled track (index 0 in shuffled playlist)
        shuffleCurrentIndex = 0;
        
        console.log(`True shuffle: Starting at shuffled position ${shuffleCurrentIndex}`);
        console.log(`Total tracks in shuffled playlist: ${shuffledIndices.length}`);
        
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
        document.getElementById('info-tab').innerHTML = `
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
    
    // Get the actual record index from shuffled playlist
    const actualIndex = getCurrentShuffledIndex();
    const currentRecord = filteredRecords[actualIndex];
    
    // Extract YouTube ID
    const youtubeId = extractYouTubeId(currentRecord.youtube_url);
    
    console.log('=== Loading shuffled track ===');
    console.log('Shuffle position:', shuffleCurrentIndex + 1, '/', shuffledIndices.length);
    console.log('Actual index:', actualIndex);
    console.log('Artist:', currentRecord.artist);
    console.log('Title:', currentRecord.title);
    console.log('Record ID:', currentRecord.id);
    console.log('YouTube ID:', youtubeId);
    
    // Update track info
    document.getElementById('trackTitle').textContent = currentRecord.title || 'Unknown Title';
    document.getElementById('trackArtist').textContent = currentRecord.artist || 'Unknown Artist';
    
    // Update price
    const priceElement = document.getElementById('trackPrice');
    if (priceElement && currentRecord.store_price) {
        priceElement.textContent = `$${parseFloat(currentRecord.store_price).toFixed(2)}`;
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
    
    // Update info tab if it's active
    if (document.querySelector('#info-tab').classList.contains('active')) {
        loadRecordInfo(actualIndex);
    }
}

// YouTube player ready callback
function onPlayerReady(event) {
    console.log('YouTube player ready');
    event.target.playVideo();
}

// YouTube player state change callback
function onPlayerStateChange(event) {
    if (event.data === 0) { // ENDED
        console.log('Video ended, playing next shuffled track...');
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

// Play previous track (using shuffled playlist)
function playPreviousTrack() {
    if (filteredRecords.length === 0) return;
    
    // Move backward in shuffled playlist
    shuffleCurrentIndex = (shuffleCurrentIndex - 1 + shuffledIndices.length) % shuffledIndices.length;
    
    console.log('Playing previous shuffled track:');
    console.log('New shuffle position:', shuffleCurrentIndex);
    
    loadCurrentYouTubeTrack();
}

// Play next track (using shuffled playlist)
function playNextTrack() {
    if (filteredRecords.length === 0) return;
    
    // Move forward in shuffled playlist
    shuffleCurrentIndex = (shuffleCurrentIndex + 1) % shuffledIndices.length;
    
    // If we reach the end of shuffled playlist, regenerate it
    if (shuffleCurrentIndex === 0) {
        console.log('End of shuffled playlist, regenerating new shuffle...');
        generateShuffledPlaylist(filteredRecords);
    }
    
    console.log('Playing next shuffled track:');
    console.log('New shuffle position:', shuffleCurrentIndex);
    
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
        
        const response = await fetch('https://arjanshaw.pythonanywhere.com/records?limit=500');
        
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

// ========== TAB MANAGEMENT ==========

// Initialize tab functionality
function initTabs() {
    const tabButtons = document.querySelectorAll('.tab-button');
    
    tabButtons.forEach(button => {
        button.addEventListener('click', function() {
            const tabId = this.getAttribute('data-tab');
            switchTab(tabId, this);
        });
    });
}

function switchTab(tabId, buttonElement) {
    // Update active tab button
    document.querySelectorAll('.tab-button').forEach(btn => {
        btn.classList.remove('active');
    });
    buttonElement.classList.add('active');
    
    // Hide all tab panes
    document.querySelectorAll('.tab-pane').forEach(pane => {
        pane.classList.remove('active');
    });
    
    // Show selected tab
    const selectedPane = document.getElementById(tabId);
    if (selectedPane) {
        selectedPane.classList.add('active');
        
        // If switching to info tab and we have filtered records, load current track info
        if (tabId === 'info-tab' && filteredRecords.length > 0) {
            const currentIndex = getCurrentShuffledIndex();
            loadRecordInfo(currentIndex);
        }
    }
}

// Load record information for the info tab
function loadRecordInfo(recordIndex) {
    const container = document.getElementById('recordInfoContainer');
    
    if (filteredRecords.length === 0 || recordIndex >= filteredRecords.length) {
        container.innerHTML = '<div class="no-record-info">No record information available</div>';
        return;
    }
    
    const record = filteredRecords[recordIndex];
    if (!record) {
        container.innerHTML = '<div class="no-record-info">No record information available</div>';
        return;
    }
    
    const artist = record.artist || 'Unknown Artist';
    const title = record.title || 'Unknown Title';
    const imageUrl = record.image_url || 'images/default-record.jpg';
    const genre = record.genre_name || 'Unknown Genre';
    const price = record.store_price ? formatPrice(record.store_price) : 'Price N/A';
    const youtubeUrl = record.youtube_url || '';
    const recordCondition = record.condition || '';
    const description = record.description || '';
    
    const hasYouTube = youtubeUrl && youtubeUrl.trim() !== '';
    const hasCondition = recordCondition && recordCondition.trim() !== '';
    
    let conditionClass = 'record-condition';
    if (hasCondition) {
        const conditionSlug = recordCondition.toLowerCase().replace(/\s+/g, '-');
        conditionClass += ` condition-${conditionSlug}`;
    }
    
    // Escape HTML to prevent XSS
    const escapeHtml = (text) => {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    };
    
    container.innerHTML = `
        <div class="record-info-card">
            <div class="record-info-image">
                <img src="${imageUrl}" alt="${escapeHtml(title)}" onerror="this.src='images/default-record.jpg'">
            </div>
            <div class="record-info-details">
                <h3>${escapeHtml(title)}</h3>
                <p class="record-info-artist">${escapeHtml(artist)}</p>
                <p class="record-info-price">${price}</p>
                <p class="record-info-genre">${escapeHtml(genre)}</p>
                
                ${hasCondition ? `
                    <p class="${conditionClass}">Condition: ${recordCondition}</p>
                ` : ''}
                
                ${description ? `
                    <div class="record-info-description">
                        <h4>Description</h4>
                        <p>${escapeHtml(description)}</p>
                    </div>
                ` : ''}
                
                ${hasYouTube ? `
                    <div class="record-info-youtube">
                        <a href="${youtubeUrl}" target="_blank" class="youtube-external-link">
                            <i class="fab fa-youtube"></i> Watch on YouTube
                        </a>
                    </div>
                ` : ''}
            </div>
        </div>
    `;
}

// Helper function to format price
function formatPrice(price) {
    if (!price) return 'Price N/A';
    const numPrice = parseFloat(price);
    return isNaN(numPrice) ? 'Price N/A' : `$${numPrice.toFixed(2)}`;
}

// ========== SCALE CONTROLS ==========

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

// ========== INITIALIZATION ==========

// Setup UI event listeners
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
    
    // Initialize tabs
    initTabs();
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded, initializing...');
    
    // Setup UI
    setupUI();
    
    // Load YouTube API
    loadYouTubeAPI();
    
    // Load records and start playing
    setTimeout(loadRecordsFromAPI, 500);
    
    // Load saved scale
    loadSavedScale();
});

// Make functions available globally
window.playPreviousTrack = playPreviousTrack;
window.playNextTrack = playNextTrack;
window.startPlaying = startPlaying;
window.scaleDown = scaleDown;
window.scaleUp = scaleUp;
window.resetScale = resetScale;