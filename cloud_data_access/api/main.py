from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import os
from typing import List, Optional, Dict, Any

# Import settings
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from config.settings import DB_PATH, API_TITLE, API_DESCRIPTION, API_VERSION, ALLOWED_ORIGINS

app = FastAPI(
    title=API_TITLE,
    description=API_DESCRIPTION,
    version=API_VERSION
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database connection
def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

# ==================== VOTING ENDPOINTS (existing functionality) ====================

@app.post("/vote/{record_id}/{voter_hash}/{vote_type}")
async def record_vote(
    record_id: int, 
    voter_hash: str, 
    vote_type: str, 
    conn: sqlite3.Connection = Depends(get_db)
):
    """Record a vote (upvote/downvote) - maintains existing voting API structure"""
    if vote_type not in ['upvote', 'downvote']:
        raise HTTPException(status_code=400, detail="Vote type must be 'upvote' or 'downvote'")
    
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT OR REPLACE INTO voter_tracking (record_id, voter_hash, vote_type)
            VALUES (?, ?, ?)
        ''', (record_id, voter_hash, vote_type))
        conn.commit()
        
        return {
            "status": "success", 
            "record_id": record_id, 
            "vote_type": vote_type,
            "voter_hash": voter_hash
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/votes/{record_id}")
async def get_votes(record_id: int, conn: sqlite3.Connection = Depends(get_db)):
    """Get vote counts for a specific record"""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT 
            SUM(CASE WHEN vote_type = 'upvote' THEN 1 ELSE 0 END) as upvotes,
            SUM(CASE WHEN vote_type = 'downvote' THEN 1 ELSE 0 END) as downvotes
        FROM voter_tracking 
        WHERE record_id = ?
    ''', (record_id,))
    
    result = cursor.fetchone()
    return {
        "record_id": record_id,
        "upvotes": result['upvotes'] or 0,
        "downvotes": result['downvotes'] or 0
    }

@app.get("/user-vote/{record_id}/{voter_hash}")
async def get_user_vote(
    record_id: int, 
    voter_hash: str, 
    conn: sqlite3.Connection = Depends(get_db)
):
    """Get a user's vote for a specific record"""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT vote_type FROM voter_tracking 
        WHERE record_id = ? AND voter_hash = ?
    ''', (record_id, voter_hash))
    
    result = cursor.fetchone()
    return {"vote_type": result['vote_type'] if result else None}

# ==================== INVENTORY ENDPOINTS (new functionality) ====================

@app.get("/records")
async def get_all_records(
    limit: Optional[int] = Query(100, ge=1, le=1000),
    offset: Optional[int] = Query(0, ge=0),
    conn: sqlite3.Connection = Depends(get_db)
):
    """Get all records with pagination - for streaming gallery and inventory management"""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT 
            r.*, 
            g.genre_name as genre,
            u.username as consignor_name,
            u.full_name as consignor_full_name,
            (SELECT COUNT(*) FROM voter_tracking WHERE record_id = r.id AND vote_type = 'upvote') as upvotes,
            (SELECT COUNT(*) FROM voter_tracking WHERE record_id = r.id AND vote_type = 'downvote') as downvotes
        FROM records r
        LEFT JOIN genres g ON r.genre_id = g.id
        LEFT JOIN users u ON r.consignor_id = u.id
        ORDER BY r.id DESC
        LIMIT ? OFFSET ?
    ''', (limit, offset))
    
    records = [dict(row) for row in cursor.fetchall()]
    return {
        "records": records,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "total": len(records)
        }
    }

@app.get("/records/{record_id}")
async def get_record(record_id: int, conn: sqlite3.Connection = Depends(get_db)):
    """Get a specific record by ID"""
    cursor = conn.cursor()
    cursor.execute('''
        SELECT 
            r.*, 
            g.genre_name as genre,
            u.username as consignor_name,
            u.full_name as consignor_full_name,
            (SELECT COUNT(*) FROM voter_tracking WHERE record_id = r.id AND vote_type = 'upvote') as upvotes,
            (SELECT COUNT(*) FROM voter_tracking WHERE record_id = r.id AND vote_type = 'downvote') as downvotes
        FROM records r
        LEFT JOIN genres g ON r.genre_id = g.id
        LEFT JOIN users u ON r.consignor_id = u.id
        WHERE r.id = ?
    ''', (record_id,))
    
    record = cursor.fetchone()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    
    return dict(record)

@app.post("/records")
async def create_record(record_data: Dict[str, Any], conn: sqlite3.Connection = Depends(get_db)):
    """Create a new record - for Streamlit app inventory management"""
    cursor = conn.cursor()
    
    try:
        # Extract fields with defaults
        cursor.execute('''
            INSERT INTO records (
                artist, title, barcode, genre_id, image_url, discogs_suggested_price,
                catalog_number, format, condition, file_at, store_price, ebay_sell_at,
                youtube_url, date_added, consignor_id, commission_rate, store_return_days, compilation
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            record_data.get('artist', ''),
            record_data.get('title', ''),
            record_data.get('barcode', ''),
            record_data.get('genre_id'),
            record_data.get('image_url', ''),
            record_data.get('discogs_suggested_price'),
            record_data.get('catalog_number', ''),
            record_data.get('format', 'Vinyl'),
            record_data.get('condition', '4'),
            record_data.get('file_at', ''),
            record_data.get('store_price'),
            record_data.get('ebay_sell_at'),
            record_data.get('youtube_url', ''),
            record_data.get('date_added'),
            record_data.get('consignor_id'),
            record_data.get('commission_rate'),
            record_data.get('store_return_days'),
            record_data.get('compilation', False)
        ))
        
        record_id = cursor.lastrowid
        conn.commit()
        
        return {
            "status": "success",
            "record_id": record_id,
            "message": "Record created successfully"
        }
        
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create record: {str(e)}")

@app.put("/records/{record_id}")
async def update_record(
    record_id: int, 
    updates: Dict[str, Any], 
    conn: sqlite3.Connection = Depends(get_db)
):
    """Update a record - for Streamlit app inventory management"""
    cursor = conn.cursor()
    
    # Check if record exists
    cursor.execute('SELECT id FROM records WHERE id = ?', (record_id,))
    if not cursor.fetchone():
        raise HTTPException(status_code=404, detail="Record not found")
    
    try:
        # Build dynamic update query
        allowed_fields = {
            'artist', 'title', 'barcode', 'genre_id', 'image_url', 'discogs_suggested_price',
            'catalog_number', 'format', 'condition', 'file_at', 'store_price', 'ebay_sell_at',
            'youtube_url', 'consignor_id', 'commission_rate', 'store_return_days', 'compilation'
        }
        
        valid_updates = {k: v for k, v in updates.items() if k in allowed_fields}
        
        if not valid_updates:
            raise HTTPException(status_code=400, detail="No valid fields to update")
        
        set_clause = ", ".join([f"{field} = ?" for field in valid_updates.keys()])
        values = list(valid_updates.values()) + [record_id]
        
        cursor.execute(f'''
            UPDATE records 
            SET {set_clause}, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', values)
        
        conn.commit()
        
        return {
            "status": "success",
            "record_id": record_id,
            "message": "Record updated successfully",
            "updated_fields": list(valid_updates.keys())
        }
        
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update record: {str(e)}")

@app.delete("/records/{record_id}")
async def delete_record(record_id: int, conn: sqlite3.Connection = Depends(get_db)):
    """Delete a record - for Streamlit app inventory management"""
    cursor = conn.cursor()
    
    # Check if record exists
    cursor.execute('SELECT id FROM records WHERE id = ?', (record_id,))
    if not cursor.fetchone():
        raise HTTPException(status_code=404, detail="Record not found")
    
    try:
        # Delete associated votes first (foreign key constraint)
        cursor.execute('DELETE FROM voter_tracking WHERE record_id = ?', (record_id,))
        
        # Delete the record
        cursor.execute('DELETE FROM records WHERE id = ?', (record_id,))
        
        conn.commit()
        
        return {
            "status": "success",
            "message": "Record deleted successfully",
            "record_id": record_id
        }
        
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete record: {str(e)}")

# ==================== UTILITY ENDPOINTS ====================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "PigStyle Cloud Data Access",
        "version": API_VERSION
    }

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "PigStyle Cloud Data Access API",
        "version": API_VERSION,
        "endpoints": {
            "voting": {
                "record_vote": "POST /vote/{record_id}/{voter_hash}/{vote_type}",
                "get_votes": "GET /votes/{record_id}",
                "get_user_vote": "GET /user-vote/{record_id}/{voter_hash}"
            },
            "inventory": {
                "get_records": "GET /records",
                "get_record": "GET /records/{record_id}",
                "create_record": "POST /records",
                "update_record": "PUT /records/{record_id}",
                "delete_record": "DELETE /records/{record_id}"
            }
        }
    }

# Run with: uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)