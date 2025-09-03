-- Migration: Add created_at and updated_at columns to menu_manager_info table
-- Run this script to add timestamp columns for consistent ordering with menu_links

-- Add created_at column
ALTER TABLE menu_manager_info 
ADD COLUMN created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;

-- Add updated_at column
ALTER TABLE menu_manager_info 
ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;

-- Update existing records to have current timestamp
UPDATE menu_manager_info 
SET created_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP 
WHERE created_at IS NULL OR updated_at IS NULL;

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_menu_manager_info_created_at ON menu_manager_info(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_menu_manager_info_updated_at ON menu_manager_info(updated_at DESC);

-- Add comment
COMMENT ON COLUMN menu_manager_info.created_at IS 'Creation timestamp';
COMMENT ON COLUMN menu_manager_info.updated_at IS 'Last update timestamp';
