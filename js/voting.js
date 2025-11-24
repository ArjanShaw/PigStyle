// Voting system for PigStyle Records - Uses artist-title as key
class VotingSystem {
    constructor() {
        this.apiBaseUrl = 'https://arjanshaw.pythonanywhere.com/api';
        this.voteCounts = {};
        this.initialized = false;
    }

    // Initialize voting system
    init() {
        if (this.initialized) return;
        
        console.log('🎵 Initializing PigStyle Voting System...');
        this.loadAllVoteCounts();
        this.attachEventListeners();
        this.initialized = true;
    }

    // Load all vote counts from API
    async loadAllVoteCounts() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/votes`);
            const data = await response.json();
            
            if (data.success) {
                this.voteCounts = data.vote_counts || {};
                this.updateAllVoteDisplays();
            } else {
                console.error('Failed to load vote counts:', data.error);
            }
        } catch (error) {
            console.error('Error loading vote counts:', error);
        }
    }

    // Load vote counts for a specific artist-title
    async loadVoteCountsForRecord(artistTitle) {
        try {
            const encodedArtistTitle = encodeURIComponent(artistTitle);
            const response = await fetch(`${this.apiBaseUrl}/votes/${encodedArtistTitle}`);
            const data = await response.json();
            
            if (data.success) {
                this.voteCounts[artistTitle] = {
                    upvotes: data.upvotes,
                    downvotes: data.downvotes
                };
                this.updateVoteDisplay(artistTitle);
                return this.voteCounts[artistTitle];
            } else {
                console.error('Failed to load vote counts for:', artistTitle, data.error);
                return { upvotes: 0, downvotes: 0 };
            }
        } catch (error) {
            console.error('Error loading vote counts for', artistTitle, error);
            return { upvotes: 0, downvotes: 0 };
        }
    }

    // Get voter hash (simple fingerprint)
    getVoterHash() {
        let hash = localStorage.getItem('pigstyle_voter_hash');
        if (!hash) {
            // Create a simple hash based on user agent and time
            hash = btoa(navigator.userAgent + Date.now()).substring(0, 16);
            localStorage.setItem('pigstyle_voter_hash', hash);
        }
        return hash;
    }

    // Record a vote using artist-title as key
    async vote(artistTitle, voteType) {
        const voterHash = this.getVoterHash();
        
        try {
            const response = await fetch(`${this.apiBaseUrl}/vote`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    artist_title: artistTitle,
                    voter_hash: voterHash,
                    vote_type: voteType
                })
            });

            const data = await response.json();
            
            if (data.success) {
                // Update local vote counts
                this.voteCounts = { ...this.voteCounts, ...data.vote_counts };
                this.updateVoteDisplay(artistTitle);
                this.showVoteFeedback(artistTitle, voteType, true);
                return true;
            } else {
                this.showVoteFeedback(artistTitle, voteType, false, data.error);
                return false;
            }
        } catch (error) {
            console.error('Error recording vote:', error);
            this.showVoteFeedback(artistTitle, voteType, false, 'Network error');
            return false;
        }
    }

    // Update display for a specific artist-title
    updateVoteDisplay(artistTitle) {
        const counts = this.voteCounts[artistTitle] || { upvotes: 0, downvotes: 0 };
        
        // Find all elements with this artist-title
        const elements = document.querySelectorAll(`[data-artist-title="${artistTitle}"]`);
        
        elements.forEach(element => {
            // Update vote buttons
            const upvoteBtn = element.querySelector('.upvote-btn');
            const downvoteBtn = element.querySelector('.downvote-btn');
            
            if (upvoteBtn) {
                const countSpan = upvoteBtn.querySelector('.vote-count') || upvoteBtn.querySelector('.upvote-count');
                if (countSpan) {
                    countSpan.textContent = counts.upvotes;
                }
            }
            
            if (downvoteBtn) {
                const countSpan = downvoteBtn.querySelector('.vote-count') || downvoteBtn.querySelector('.downvote-count');
                if (countSpan) {
                    countSpan.textContent = counts.downvotes;
                }
            }
            
            // Update any standalone vote displays
            const voteDisplay = element.querySelector('.vote-display');
            if (voteDisplay) {
                voteDisplay.innerHTML = `
                    <span class="upvote-count">${counts.upvotes}</span> 👍 | 
                    <span class="downvote-count">${counts.downvotes}</span> 👎
                `;
            }
        });
    }

    // Update all vote displays
    updateAllVoteDisplays() {
        for (const artistTitle in this.voteCounts) {
            this.updateVoteDisplay(artistTitle);
        }
    }

    // Show vote feedback
    showVoteFeedback(artistTitle, voteType, success, errorMessage = '') {
        // Find the record element
        const elements = document.querySelectorAll(`[data-artist-title="${artistTitle}"]`);
        if (!elements.length) return;

        elements.forEach(element => {
            // Create or find feedback element
            let feedbackEl = element.querySelector('.vote-feedback');
            if (!feedbackEl) {
                feedbackEl = document.createElement('div');
                feedbackEl.className = 'vote-feedback';
                element.appendChild(feedbackEl);
            }

            if (success) {
                feedbackEl.textContent = `✓ ${voteType === 'upvote' ? 'Liked' : 'Disliked'}!`;
                feedbackEl.className = 'vote-feedback success';
            } else {
                feedbackEl.textContent = errorMessage || 'Vote failed. Try again.';
                feedbackEl.className = 'vote-feedback error';
            }

            // Remove feedback after 3 seconds
            setTimeout(() => {
                if (feedbackEl.parentNode) {
                    feedbackEl.remove();
                }
            }, 3000);
        });
    }

    // Attach event listeners to vote buttons
    attachEventListeners() {
        document.addEventListener('click', (event) => {
            // Upvote button
            if (event.target.closest('.upvote-btn')) {
                const btn = event.target.closest('.upvote-btn');
                const artistTitle = btn.getAttribute('data-artist-title');
                if (artistTitle) {
                    this.vote(artistTitle, 'upvote');
                }
            }
            
            // Downvote button
            if (event.target.closest('.downvote-btn')) {
                const btn = event.target.closest('.downvote-btn');
                const artistTitle = btn.getAttribute('data-artist-title');
                if (artistTitle) {
                    this.vote(artistTitle, 'downvote');
                }
            }
        });
    }

    // Get current vote counts for an artist-title
    getVoteCounts(artistTitle) {
        return this.voteCounts[artistTitle] || { upvotes: 0, downvotes: 0 };
    }
}

// Initialize voting system when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    window.pigstyleVoting = new VotingSystem();
    window.pigstyleVoting.init();
});

// Export for module use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = VotingSystem;
}