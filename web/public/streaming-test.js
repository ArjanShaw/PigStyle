console.log('streaming-test.js loaded! Testing purchase button.');

// ========== GLOBAL VARIABLES ==========
let allRecords = [];
let filteredRecords = [];
let shuffledIndices = [];
let shuffleCurrentIndex = 0;
let youtubePlayer = null;
let youtubeAPILoaded = false;
let allGenres = [];
let selectedGenres = new Set();

// ========== 新增: “立即购买” 按钮逻辑 ==========
function setupBuyNowButton(currentRecord) {
    const buyButton = document.getElementById('buyNowBtn');
    
    // 条件: 如果商品有ID、有价格，并且有YouTube视频（根据你的需求可选）
    // 此处我们假设你只想为有YouTube视频的商品显示购买按钮
    const isPurchasable = currentRecord && currentRecord.id && currentRecord.store_price && currentRecord.youtube_url;
    
    if (buyButton && isPurchasable) {
        // 动态构建 WooCommerce 产品页面 URL (将 your-store.com 替换为你的真实域名)
        const wooCommercePageUrl = 'https://your-woocommerce-store.com/buy-record'; // <<< 重要：请修改此行
        const dynamicProductUrl = `${wooCommercePageUrl}?record_id=${currentRecord.id}`;
        
        buyButton.onclick = function() {
            window.open(dynamicProductUrl, '_blank');
            console.log('Opening purchase page for:', currentRecord.id, dynamicProductUrl);
        };
        
        buyButton.style.display = 'block';
        console.log('Buy Now button ENABLED for:', currentRecord.artist, '-', currentRecord.title);
        
    } else {
        // 如果没有YouTube视频，则隐藏购买按钮
        if (buyButton) {
            buyButton.style.display = 'none';
            console.log('Buy Now button HIDDEN (no YouTube video for this track).');
        }
    }
}

// ========== YOUTUBE PLAYER FUNCTIONS ==========
function loadYouTubeAPI() {
    if (window.YT && window.YT.Player) {
        youtubeAPILoaded = true;
        return;
    }
    const tag = document.createElement('script');
    tag.src = 'https://www.youtube.com/iframe_api';
    const firstScriptTag = document.getElementsByTagName('script')[0];
    firstScriptTag.parentNode.insertBefore(tag, firstScriptTag);
}

window.onYouTubeIframeAPIReady = function() {
    youtubeAPILoaded = true;
    if (filteredRecords.length > 0) {
        loadCurrentYouTubeTrack();
    }
};

// ========== SHUFFLE FUNCTIONS ==========
function generateShuffledPlaylist(records) {
    shuffledIndices = Array.from({ length: records.length }, (_, i) => i);
    for (let i = shuffledIndices.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [shuffledIndices[i], shuffledIndices[j]] = [shuffledIndices[j], shuffledIndices[i]];
    }
    shuffleCurrentIndex = 0;
}

function getCurrentShuffledIndex() {
    if (shuffledIndices.length === 0) return 0;
    return shuffledIndices[shuffleCurrentIndex];
}

// ========== GENRE MANAGEMENT ==========
function extractUniqueGenres(records) {
    const genreSet = new Set();
    records.forEach(record => {
        if (record.genre_name && record.youtube_url) {
            const hasYouTube = record.youtube_url.includes('youtube.com') || record.youtube_url.includes('youtu.be');
            if (hasYouTube) {
                genreSet.add(record.genre_name);
            }
        }
    });
    allGenres = Array.from(genreSet).sort();
    return allGenres;
}

function initGenreCheckboxes() {
    const container = document.getElementById('genreCheckboxContainer');
    container.innerHTML = '';
    
    const header = document.createElement('div');
    header.className = 'genre-checkbox-header';
    header.innerHTML = '<h3>Filter by Genre</h3>';
    container.appendChild(header);
    
    const group = document.createElement('div');
    group.className = 'genre-checkbox-group';
    
    allGenres.forEach(genre => {
        const item = document.createElement('div');
        item.className = 'genre-checkbox-item';
        
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.id = `genre-${genre.replace(/\s+/g, '-').toLowerCase()}`;
        checkbox.value = genre;
        checkbox.checked = selectedGenres.has(genre);
        checkbox.addEventListener('change', (e) => {
            if (e.target.checked) {
                selectedGenres.add(genre);
            } else {
                selectedGenres.delete(genre);
            }
            applyGenreFilter();
            saveSelections();
        });
        
        const label = document.createElement('label');
        label.htmlFor = `genre-${genre.replace(/\s+/g, '-').toLowerCase()}`;
        label.textContent = genre;
        
        item.appendChild(checkbox);
        item.appendChild(label);
        group.appendChild(item);
    });
    
    container.appendChild(group);
    
    const actions = document.createElement('div');
    actions.className = 'genre-actions';
    
    const selectAllBtn = document.createElement('button');
    selectAllBtn.className = 'genre-action-btn genre-select-all';
    selectAllBtn.textContent = 'Select All';
    selectAllBtn.addEventListener('click', () => {
        selectedGenres = new Set(allGenres);
        updateCheckboxes();
        applyGenreFilter();
        saveSelections();
    });
    
    const deselectAllBtn = document.createElement('button');
    deselectAllBtn.className = 'genre-action-btn genre-deselect-all';
    deselectAllBtn.textContent = 'Deselect All';
    deselectAllBtn.addEventListener('click', () => {
        selectedGenres.clear();
        updateCheckboxes();
        applyGenreFilter();
        saveSelections();
    });
    
    const applyBtn = document.createElement('button');
    applyBtn.className = 'genre-action-btn genre-apply';
    applyBtn.textContent = 'Close';
    applyBtn.addEventListener('click', () => {
        document.getElementById('genreCheckboxContainer').classList.remove('show');
        document.getElementById('genreToggleBtn').classList.remove('active');
    });
    
    actions.appendChild(selectAllBtn);
    actions.appendChild(deselectAllBtn);
    actions.appendChild(applyBtn);
    container.appendChild(actions);
}

function updateCheckboxes() {
    allGenres.forEach(genre => {
        const checkbox = document.getElementById(`genre-${genre.replace(/\s+/g, '-').toLowerCase()}`);
        if (checkbox) {
            checkbox.checked = selectedGenres.has(genre);
        }
    });
}

function applyGenreFilter() {
    if (selectedGenres.size === 0) {
        filteredRecords = [];
    } else {
        filteredRecords = allRecords.filter(record => 
            record.youtube_url && 
            (record.youtube_url.includes('youtube.com') || record.youtube_url.includes('youtu.be')) &&
            record.genre_name &&
            selectedGenres.has(record.genre_name)
        );
    }
    
    if (filteredRecords.length > 0) {
        generateShuffledPlaylist(filteredRecords);
        shuffleCurrentIndex = 0;
        if (youtubeAPILoaded) {
            loadCurrentYouTubeTrack();
        }
        document.getElementById('youtubeControls').style.display = 'flex';
    } else {
        if (youtubePlayer) {
            youtubePlayer.destroy();
            youtubePlayer = null;
        }
        document.getElementById('youtube-player').innerHTML = `
            <div style="padding: 40px; text-align: center; color: white;">
                <h3>No Tracks Found</h3>
                <p>No YouTube videos found for selected genre(s).</p>
            </div>
        `;
        document.getElementById('youtubeControls').style.display = 'none';
        document.getElementById('trackTitle').textContent = 'No Tracks Available';
        document.getElementById('trackArtist').textContent = 'Select genres to see tracks';
        document.getElementById('trackPrice').textContent = '';
        
        // 当没有曲目时，隐藏购买按钮
        document.getElementById('buyNowBtn').style.display = 'none';
    }
}

// ========== CORE PLAYER FUNCTIONS ==========
function loadSavedSelections() {
    const savedGenres = localStorage.getItem('pigstyleStreamingGenres');
    if (savedGenres) {
        try {
            const parsedGenres = JSON.parse(savedGenres);
            if (Array.isArray(parsedGenres)) {
                const validGenres = parsedGenres.filter(genre => allGenres.includes(genre));
                selectedGenres = validGenres.length > 0 ? new Set(validGenres) : new Set(allGenres);
            } else {
                selectedGenres = new Set(allGenres);
            }
        } catch (e) {
            selectedGenres = new Set(allGenres);
        }
    } else {
        selectedGenres = new Set(allGenres);
    }
}

function saveSelections() {
    const genresToSave = Array.from(selectedGenres);
    localStorage.setItem('pigstyleStreamingGenres', JSON.stringify(genresToSave));
}

function startYouTubePlayback() {
    if (youtubePlayer) {
        youtubePlayer.destroy();
        youtubePlayer = null;
    }
    
    document.getElementById('loading').style.display = 'none';
    document.getElementById('playerContent').style.display = 'block';
    document.getElementById('youtubeContainer').style.display = 'block';
    
    if (!youtubeAPILoaded) {
        loadYouTubeAPI();
    }
    
    applyGenreFilter();
}

function loadCurrentYouTubeTrack() {
    if (filteredRecords.length === 0) return;
    
    const actualIndex = getCurrentShuffledIndex();
    const currentRecord = filteredRecords[actualIndex];
    const youtubeId = extractYouTubeId(currentRecord.youtube_url);
    
    // 更新曲目信息
    document.getElementById('trackTitle').textContent = currentRecord.title || 'Unknown Title';
    document.getElementById('trackArtist').textContent = currentRecord.artist || 'Unknown Artist';
    const priceElement = document.getElementById('trackPrice');
    if (priceElement && currentRecord.store_price) {
        priceElement.textContent = `$${parseFloat(currentRecord.store_price).toFixed(2)}`;
    }
    
    // === 关键部分：设置“立即购买”按钮 ===
    setupBuyNowButton(currentRecord);
    
    // 原有的YouTube播放器加载逻辑
    if (!youtubeId) {
        document.getElementById('youtube-player').innerHTML = `
            <div style="padding: 40px; text-align: center; color: white;">
                <h3>No YouTube Video Available</h3>
                <p>Track: ${currentRecord.artist} - ${currentRecord.title}</p>
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
    
    if (document.querySelector('#info-tab').classList.contains('active')) {
        loadRecordInfo(actualIndex);
    }
}

function onPlayerReady(event) {
    event.target.playVideo();
}

function onPlayerStateChange(event) {
    if (event.data === 0) {
        playNextTrack();
    }
}

function onPlayerError(event) {
    setTimeout(playNextTrack, 3000);
}

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

function playPreviousTrack() {
    if (filteredRecords.length === 0) return;
    shuffleCurrentIndex = (shuffleCurrentIndex - 1 + shuffledIndices.length) % shuffledIndices.length;
    loadCurrentYouTubeTrack();
}

function playNextTrack() {
    if (filteredRecords.length === 0) return;
    shuffleCurrentIndex = (shuffleCurrentIndex + 1) % shuffledIndices.length;
    if (shuffleCurrentIndex === 0) {
        generateShuffledPlaylist(filteredRecords);
    }
    loadCurrentYouTubeTrack();
}

// ========== DATA LOADING ==========
async function loadRecordsFromAPI() {
    try {
        const response = await fetch('https://arjanshaw.pythonanywhere.com/records/random?limit=500&has_youtube=true');
        if (!response.ok) throw new Error(`API error: ${response.status}`);
        const data = await response.json();
        if (data && data.status === 'success' && data.records) {
            allRecords = data.records;
            extractUniqueGenres(allRecords);
            loadSavedSelections();
            initGenreCheckboxes();
            updateCheckboxes();
            saveSelections();
            startYouTubePlayback();
        } else {
            throw new Error('Invalid response from API');
        }
    } catch (error) {
        console.error('Error loading records:', error);
        document.getElementById('youtube-player').innerHTML = `
            <div style="padding: 40px; text-align: center; color: white;">
                <h3>Error Loading Records</h3>
                <p>${error.message}</p>
            </div>
        `;
    }
}

// ========== TAB MANAGEMENT ==========
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
    document.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active'));
    buttonElement.classList.add('active');
    document.querySelectorAll('.tab-pane').forEach(pane => pane.classList.remove('active'));
    const selectedPane = document.getElementById(tabId);
    if (selectedPane) {
        selectedPane.classList.add('active');
        if (tabId === 'info-tab' && filteredRecords.length > 0) {
            const currentIndex = getCurrentShuffledIndex();
            loadRecordInfo(currentIndex);
        }
    }
}

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
    
    const escapeHtml = (text) => {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    };
    
    container.innerHTML = `
        <div class="record-info-card">
            <div class="record-info-image">
                <img src="${record.image_url}" alt="${escapeHtml(record.title)}" onerror="this.src='images/default-record.jpg'">
            </div>
            <div class="record-info-details">
                <h3>${escapeHtml(record.title)}</h3>
                <p class="record-info-artist">${escapeHtml(record.artist)}</p>
                <p class="record-info-price">$${parseFloat(record.store_price || 0).toFixed(2)}</p>
                <p class="record-info-genre">${escapeHtml(record.genre_name)}</p>
            </div>
        </div>
    `;
}

// ========== SCALE CONTROLS ==========
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
    const scalePercent = document.getElementById('scalePercent');
    if (scalePercent) {
        scalePercent.textContent = `${Math.round(currentScale * 100)}%`;
    }
    localStorage.setItem('pigstyleStreamingScale', currentScale);
}

function loadSavedScale() {
    const savedScale = localStorage.getItem('pigstyleStreamingScale');
    if (savedScale) {
        currentScale = parseFloat(savedScale);
        currentScale = Math.max(0.5, Math.min(2.0, currentScale));
        setTimeout(() => applyScale(), 500);
    }
}

// ========== UI SETUP ==========
function setupUI() {
    const genreToggleBtn = document.getElementById('genreToggleBtn');
    if (genreToggleBtn) {
        genreToggleBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            const container = document.getElementById('genreCheckboxContainer');
            const btn = document.getElementById('genreToggleBtn');
            container.classList.toggle('show');
            btn.classList.toggle('active');
        });
    }
    
    document.addEventListener('click', (e) => {
        const container = document.getElementById('genreCheckboxContainer');
        const btn = document.getElementById('genreToggleBtn');
        if (container && btn && !container.contains(e.target) && !btn.contains(e.target)) {
            container.classList.remove('show');
            btn.classList.remove('active');
        }
    });
    
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    if (prevBtn) prevBtn.addEventListener('click', playPreviousTrack);
    if (nextBtn) nextBtn.addEventListener('click', playNextTrack);
    
    initTabs();
}

// ========== INITIALIZATION ==========
document.addEventListener('DOMContentLoaded', function() {
    console.log('Test environment loaded.');
    setupUI();
    loadYouTubeAPI();
    setTimeout(loadRecordsFromAPI, 500);
    loadSavedScale();
});

// 全局函数
window.playPreviousTrack = playPreviousTrack;
window.playNextTrack = playNextTrack;
window.scaleDown = scaleDown;
window.scaleUp = scaleUp;
window.resetScale = resetScale;