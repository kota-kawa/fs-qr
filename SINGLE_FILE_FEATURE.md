# Single File Encryption Feature

## Overview

This feature adds support for optimized single file encryption in the FS!QR application. When uploading a single file, the application now encrypts only the file (without ZIP compression) for improved efficiency, while maintaining backward compatibility with multiple file uploads.

## Changes Made

### Frontend (fs-qr-upload.html)
- Modified `encryptAndZipFilesWithProgress()` function to detect single vs multiple files
- Single file: AES-GCM encryption only (no ZIP)
- Multiple files: Existing ZIP + encryption behavior unchanged
- Added file type detection and original filename preservation

### Backend (core_app.py)
- Updated `/upload` endpoint to handle `file_type` parameter
- Modified `/download_go` endpoint to serve appropriate file format
- Added support for both `.enc` (single files) and `.zip` (multiple files) storage

### Frontend Download (info.html)
- Added `decryptSingleFile()` function for single file decryption
- Modified download logic to detect file type from response headers
- Maintains backward compatibility with existing ZIP file downloads

### Database Schema
- Added `file_type` column to track single vs multiple file uploads
- Added `original_filename` column for single file name preservation
- Migration script provided: `db_init/migrate_add_file_type.sql`

## Database Migration

For existing installations, run:
```sql
ALTER TABLE fsqr 
ADD COLUMN file_type VARCHAR(20) DEFAULT 'multiple',
ADD COLUMN original_filename VARCHAR(255) DEFAULT NULL;
```

## Behavior

### Single File Upload
1. User selects one file
2. File is encrypted with AES-GCM (no ZIP compression)
3. Stored as `{secure_id}.enc`
4. Original filename preserved in database

### Multiple File Upload  
1. User selects multiple files
2. Files are encrypted and ZIPped (existing behavior)
3. Stored as `{secure_id}.zip`
4. Maintains full backward compatibility

### Download
- Single files: Direct decryption and download with original filename
- Multiple files: ZIP decryption and download (existing behavior)
- File type automatically detected from database and response headers

## Benefits

1. **Efficiency**: Single files avoid unnecessary ZIP compression
2. **Performance**: Faster encryption/decryption for single files
3. **Compatibility**: Zero breaking changes to existing functionality
4. **User Experience**: Original filenames preserved for single files