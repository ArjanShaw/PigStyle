class VotingSystem {
    constructor() {
        this.apiBaseUrl = 'http://localhost:5000'; // Update with your Flask API URL
        this.currentTrack = null;
        this.userIP = null;
    }

    async initialize() {
        await this.getUserIP();
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
            // Fallback to a random identifier
            this.userIP = 'unknown_' + Math.random().toString(36).substr(2, 9);
        }
    }

    setupVoteHandlers() {
        // These will be called when votes buttons are clicked
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('upvote-btn')) {
                this.handleVote('upvote');
            } else if (e.target.classList.contains('downvote-btn')) {
                this.handleVote('downvote');
            }
        });
    }

    async loadCurrentTrack(record) {
        this.currentTrack = {
            artist: record.artist,
            title: record.title
        };
        
        await this.updateVoteDisplay();
    }

    async updateVoteDisplay() {
        if (!this.currentTrack) return;

        try {
            const response = await fetch(
                `${this.apiBaseUrl}/votes/${encodeURIComponent(this.currentTrack.artist)}/${encodeURIComponent(this.currentTrack.title)}`
            );
            
            if (response.ok) {
                const data = await response.json();
                
                // Update vote counts in UI
                const upvoteBtn = document.querySelector('.upvote-btn');
                const downvoteBtn = document.querySelector('.downvote-btn');
                const upvoteCount = document.querySelector('.upvote-count');
                const downvoteCount = document.querySelector('.downvote-count');
                
                if (upvoteCount) upvoteCount.textContent = data.upvotes;
                if (downvoteCount) downvoteCount.textContent = data.downvotes;
                
                // Update button states
                if (upvoteBtn && downvoteBtn) {
                    upvoteBtn.classList.remove('voted');
                    downvoteBtn.classList.remove('voted');
                    
                    if (data.user_vote === 'upvote') {
                        upvoteBtn.classList.add('voted');
                    } else if (data.user_vote === 'downvote') {
                        downvoteBtn.classList.add('voted');
                    }
                }
            }
        } catch (error) {
            console.error('Error fetching votes:', error);
        }
    }

    async handleVote(voteType) {
        if (!this.currentTrack) return;

        try {
            const response = await fetch(`${this.apiBaseUrl}/vote`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    artist: this.currentTrack.artist,
                    title: this.currentTrack.title,
                    vote_type: voteType
                })
            });

            if (response.ok) {
                const result = await response.json();
                console.log('Vote successful:', result.message);
                await this.updateVoteDisplay();
            } else {
                const error = await response.json();
                console.error('Vote failed:', error.error);
            }
        } catch (error) {
            console.error('Error submitting vote:', error);
        }
    }
}

// Initialize voting system when page loads
document.addEventListener('DOMContentLoaded', async () => {
    const votingSystem = new VotingSystem();
    await votingSystem.initialize();
    
    // Example: When a new track loads in your streaming system
    // votingSystem.loadCurrentTrack({
    //     artist: 'Current Artist',
    //     title: 'Current Title'
    // });
});