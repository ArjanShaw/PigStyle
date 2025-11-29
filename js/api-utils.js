// Shared API utilities for PigStyle Records
class PigStyleAPI {
    constructor() {
        this.API_BASE_URL = 'https://arjanshaw.pythonanywhere.com';
    }

    // Load all records from the API
    async loadAllRecords() {
        try {
            console.log('Loading records from API...');
            const response = await fetch(`${this.API_BASE_URL}/records?limit=1000`);
            
            if (!response.ok) {
                throw new Error(`API error: ${response.status}`);
            }
            
            const data = await response.json();
            
            // Handle both data structures
            if (data && data.records && Array.isArray(data.records)) {
                console.log(`Loaded ${data.records.length} records from API`);
                return data.records;
            } else if (Array.isArray(data)) {
                console.log(`Loaded ${data.length} records from API (direct array)`);
                return data;
            } else {
                console.error('Unexpected API response structure:', data);
                return [];
            }
        } catch (error) {
            console.error('Error loading records from API:', error);
            throw error;
        }
    }

    // Extract YouTube ID from URL
    extractYouTubeId(url) {
        if (!url) return null;
        
        const patterns = [
            /(?:youtube\.com\/watch\?v=|youtu\.be\/)([^&\n?]+)/,
            /youtube\.com\/embed\/([^&\n?]+)/,
            /youtube\.com\/v\/([^&\n?]+)/
        ];
        
        for (const pattern of patterns) {
            const match = url.match(pattern);
            if (match) {
                return match[1];
            }
        }
        return null;
    }

    // Filter records that have YouTube videos
    filterStreamableRecords(records) {
        return records.filter(record => this.extractYouTubeId(record.youtube_url) !== null);
    }

    // Get unique genres from records
    getUniqueGenres(records) {
        return [...new Set(records.map(record => record.genre))].sort();
    }

    // Get unique artists from records
    getUniqueArtists(records) {
        return [...new Set(records.map(record => record.artist))].sort();
    }

    // Helper function to escape HTML
    escapeHtml(text) {
        if (typeof text !== 'string') return text;
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize global API instance
window.pigstyleAPI = new PigStyleAPI();