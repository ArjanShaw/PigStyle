import streamlit as st
import os
import json
import hashlib
from database_manager import DatabaseManager

def create_voter_hash(ip_address, user_agent):
    """Create a hash for voter identification without storing raw IP"""
    hash_input = f"{ip_address}:{user_agent}"
    return hashlib.md5(hash_input.encode()).hexdigest()

def main():
    st.title("PigStyle Records Voting API")
    
    # Initialize database manager
    db_manager = DatabaseManager()
    
    # Get request details using st.query_params
    query_params = st.query_params
    ip_address = query_params.get('ip', [''])[0]
    user_agent = query_params.get('user_agent', [''])[0]
    
    if not ip_address or not user_agent:
        st.error("Missing IP address or user agent")
        return
    
    voter_hash = create_voter_hash(ip_address, user_agent)
    
    # Handle different endpoints
    endpoint = query_params.get('endpoint', [''])[0]
    
    if endpoint == 'vote':
        handle_vote_endpoint(db_manager, voter_hash, query_params)
    elif endpoint == 'votes':
        handle_votes_endpoint(db_manager, query_params)
    else:
        st.error("Invalid endpoint")
    
def handle_vote_endpoint(db_manager, voter_hash, query_params):
    """Handle vote submission"""
    record_id = query_params.get('record_id', [''])[0]
    vote_type = query_params.get('vote_type', [''])[0]
    
    if not record_id or not vote_type:
        st.error("Missing record_id or vote_type")
        return
    
    if vote_type not in ['upvote', 'downvote']:
        st.error("Invalid vote_type. Must be 'upvote' or 'downvote'")
        return
    
    try:
        record_id = int(record_id)
    except ValueError:
        st.error("Invalid record_id")
        return
    
    # Record the vote
    success = db_manager.record_vote(record_id, voter_hash, vote_type)
    
    if success:
        # Get updated vote counts
        vote_counts = db_manager.get_vote_counts(record_id)
        response = {
            'success': True,
            'record_id': record_id,
            'vote_type': vote_type,
            'vote_counts': vote_counts.get(record_id, {'upvotes': 0, 'downvotes': 0})
        }
    else:
        response = {
            'success': False,
            'error': 'Failed to record vote'
        }
    
    st.json(response)

def handle_votes_endpoint(db_manager, query_params):
    """Handle vote counts retrieval"""
    record_id = query_params.get('record_id', [''])[0]
    
    if record_id:
        try:
            record_id = int(record_id)
            vote_counts = db_manager.get_vote_counts(record_id)
        except ValueError:
            st.error("Invalid record_id")
            return
    else:
        vote_counts = db_manager.get_vote_counts()
    
    response = {
        'success': True,
        'vote_counts': vote_counts
    }
    
    st.json(response)

if __name__ == "__main__":
    main()