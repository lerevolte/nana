DROP DATABASE IF EXISTS image_bot_db;

CREATE DATABASE image_bot_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE image_bot_db;

DROP TABLE IF EXISTS users;

CREATE TABLE users (
  id BIGINT PRIMARY KEY,
  username VARCHAR(255),
  first_name VARCHAR(255),
  generations_balance INT DEFAULT 3,
  selected_model VARCHAR(100) DEFAULT 'google/nano-banana',
  selected_aspect_ratio VARCHAR(20) DEFAULT 'match_input_image',
  has_received_welcome_bonus BOOLEAN DEFAULT FALSE,
  last_free_generation_date DATE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_id ON users(id);