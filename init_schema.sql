-- Extensions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Users
ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS interests TEXT[];
ALTER TABLE IF EXISTS users ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMP;

-- Content
CREATE TABLE IF NOT EXISTS content (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title VARCHAR(500) NOT NULL,
  description TEXT,
  content_type VARCHAR(50) NOT NULL,
  thumbnail_url VARCHAR(500),
  trailer_url VARCHAR(500),
  release_date DATE,
  duration INTEGER,
  language VARCHAR(10) DEFAULT 'fr',
  country VARCHAR(100),
  age_rating VARCHAR(10),
  tags TEXT[],
  genres TEXT[],
  cast_members JSONB,
  directors JSONB,
  is_premium BOOLEAN DEFAULT FALSE,
  is_published BOOLEAN DEFAULT FALSE,
  view_count INTEGER DEFAULT 0,
  like_count INTEGER DEFAULT 0,
  created_by UUID REFERENCES users(id),
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Seasons
CREATE TABLE IF NOT EXISTS seasons (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  content_id UUID NOT NULL REFERENCES content(id) ON DELETE CASCADE,
  season_number INTEGER NOT NULL,
  title VARCHAR(300),
  description TEXT,
  release_date DATE,
  thumbnail_url VARCHAR(500),
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(content_id, season_number)
);

-- Episodes
CREATE TABLE IF NOT EXISTS episodes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  season_id UUID NOT NULL REFERENCES seasons(id) ON DELETE CASCADE,
  episode_number INTEGER NOT NULL,
  title VARCHAR(300) NOT NULL,
  description TEXT,
  video_url VARCHAR(500),
  thumbnail_url VARCHAR(500),
  duration INTEGER,
  is_free BOOLEAN DEFAULT FALSE,
  view_count INTEGER DEFAULT 0,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(season_id, episode_number)
);

-- Videos (standalone)
CREATE TABLE IF NOT EXISTS videos (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title VARCHAR(300) NOT NULL,
  description TEXT,
  video_url VARCHAR(500),
  thumbnail_url VARCHAR(500),
  duration INTEGER,
  view_count INTEGER DEFAULT 0,
  like_count INTEGER DEFAULT 0,
  share_count INTEGER DEFAULT 0,
  is_premium BOOLEAN DEFAULT FALSE,
  is_published BOOLEAN DEFAULT FALSE,
  tags TEXT[],
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Concerts
CREATE TABLE IF NOT EXISTS concerts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title VARCHAR(300) NOT NULL,
  description TEXT,
  artist_name VARCHAR(200),
  venue VARCHAR(300),
  city VARCHAR(200),
  country VARCHAR(100),
  event_date TIMESTAMP,
  end_date TIMESTAMP,
  thumbnail_url VARCHAR(500),
  stream_url VARCHAR(500),
  is_live BOOLEAN DEFAULT FALSE,
  is_premium BOOLEAN DEFAULT FALSE,
  ticket_price DECIMAL(10,2),
  max_attendees INTEGER,
  current_attendees INTEGER DEFAULT 0,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Events
CREATE TABLE IF NOT EXISTS events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title VARCHAR(300) NOT NULL,
  description TEXT,
  event_type VARCHAR(50),
  venue VARCHAR(300),
  city VARCHAR(200),
  country VARCHAR(100),
  start_date TIMESTAMP,
  end_date TIMESTAMP,
  thumbnail_url VARCHAR(500),
  is_online BOOLEAN DEFAULT FALSE,
  stream_url VARCHAR(500),
  is_premium BOOLEAN DEFAULT FALSE,
  ticket_price DECIMAL(10,2),
  max_attendees INTEGER,
  current_attendees INTEGER DEFAULT 0,
  tags TEXT[],
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Subscriptions
CREATE TABLE IF NOT EXISTS subscriptions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  subscriber_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  creator_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  plan VARCHAR(50) DEFAULT 'basic',
  price DECIMAL(10,2),
  currency VARCHAR(10) DEFAULT 'XOF',
  status VARCHAR(20) DEFAULT 'active',
  started_at TIMESTAMP DEFAULT NOW(),
  expires_at TIMESTAMP,
  stripe_subscription_id VARCHAR(200),
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(subscriber_id, creator_id)
);

-- Payments
CREATE TABLE IF NOT EXISTS payments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  subscription_id UUID REFERENCES subscriptions(id),
  amount DECIMAL(10,2) NOT NULL,
  currency VARCHAR(10) DEFAULT 'XOF',
  status VARCHAR(20) DEFAULT 'pending',
  payment_method VARCHAR(50),
  provider VARCHAR(50),
  provider_transaction_id VARCHAR(200),
  description TEXT,
  metadata JSONB,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Tickets (concerts)
CREATE TABLE IF NOT EXISTS tickets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  concert_id UUID REFERENCES concerts(id),
  payment_id UUID REFERENCES payments(id),
  ticket_code VARCHAR(100) UNIQUE,
  status VARCHAR(20) DEFAULT 'valid',
  price DECIMAL(10,2),
  seat_info VARCHAR(200),
  used_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Event Tickets
CREATE TABLE IF NOT EXISTS event_tickets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  event_id UUID REFERENCES events(id),
  payment_id UUID REFERENCES payments(id),
  ticket_code VARCHAR(100) UNIQUE,
  status VARCHAR(20) DEFAULT 'valid',
  price DECIMAL(10,2),
  seat_info VARCHAR(200),
  used_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Reels
CREATE TABLE IF NOT EXISTS reels (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  caption TEXT,
  video_url VARCHAR(500),
  thumbnail_url VARCHAR(500),
  audio_url VARCHAR(500),
  duration INTEGER,
  view_count INTEGER DEFAULT 0,
  like_count INTEGER DEFAULT 0,
  share_count INTEGER DEFAULT 0,
  comment_count INTEGER DEFAULT 0,
  tags TEXT[],
  music_title VARCHAR(200),
  music_artist VARCHAR(200),
  is_published BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Stories
CREATE TABLE IF NOT EXISTS stories (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  media_url VARCHAR(500),
  media_type VARCHAR(20) DEFAULT 'image',
  thumbnail_url VARCHAR(500),
  caption TEXT,
  duration_sec INTEGER DEFAULT 5,
  background_color VARCHAR(50),
  audio_url VARCHAR(500),
  font_style VARCHAR(50),
  view_count INTEGER DEFAULT 0,
  expires_at TIMESTAMP DEFAULT NOW() + INTERVAL '24 hours',
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Comments
CREATE TABLE IF NOT EXISTS comments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  content_id UUID REFERENCES content(id) ON DELETE CASCADE,
  reel_id UUID REFERENCES reels(id) ON DELETE CASCADE,
  video_id UUID REFERENCES videos(id) ON DELETE CASCADE,
  parent_id UUID REFERENCES comments(id) ON DELETE CASCADE,
  text TEXT NOT NULL,
  like_count INTEGER DEFAULT 0,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Reactions
CREATE TABLE IF NOT EXISTS reactions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  content_id UUID REFERENCES content(id) ON DELETE CASCADE,
  reel_id UUID REFERENCES reels(id) ON DELETE CASCADE,
  video_id UUID REFERENCES videos(id) ON DELETE CASCADE,
  comment_id UUID REFERENCES comments(id) ON DELETE CASCADE,
  concert_id UUID REFERENCES concerts(id) ON DELETE CASCADE,
  event_id UUID REFERENCES events(id) ON DELETE CASCADE,
  reaction_type VARCHAR(20) DEFAULT 'like',
  created_at TIMESTAMP DEFAULT NOW()
);

-- Shares
CREATE TABLE IF NOT EXISTS shares (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  content_id UUID REFERENCES content(id) ON DELETE CASCADE,
  reel_id UUID REFERENCES reels(id) ON DELETE CASCADE,
  video_id UUID REFERENCES videos(id) ON DELETE CASCADE,
  platform VARCHAR(50),
  created_at TIMESTAMP DEFAULT NOW()
);

-- Follows
CREATE TABLE IF NOT EXISTS follows (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  follower_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  following_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(follower_id, following_id)
);

-- User Interests
CREATE TABLE IF NOT EXISTS user_interests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  interest VARCHAR(100) NOT NULL,
  created_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(user_id, interest)
);

-- Messages conversations
CREATE TABLE IF NOT EXISTS conversations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  participant1_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  participant2_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  last_message_id UUID,
  last_message_at TIMESTAMP,
  participant1_unread INTEGER DEFAULT 0,
  participant2_unread INTEGER DEFAULT 0,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(participant1_id, participant2_id)
);

-- Messages
CREATE TABLE IF NOT EXISTS messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  sender_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  content TEXT,
  media_url VARCHAR(500),
  media_type VARCHAR(20),
  is_read BOOLEAN DEFAULT FALSE,
  read_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW()
);

-- FK deferred pour last_message_id
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE constraint_name = 'fk_last_message' AND table_name = 'conversations'
  ) THEN
    ALTER TABLE conversations ADD CONSTRAINT fk_last_message
      FOREIGN KEY (last_message_id) REFERENCES messages(id) DEFERRABLE INITIALLY DEFERRED;
  END IF;
END $$;

-- Notification tokens
CREATE TABLE IF NOT EXISTS notification_tokens (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token VARCHAR(500) NOT NULL,
  platform VARCHAR(20),
  created_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(user_id, token)
);

-- Migration: font_style pour stories texte
ALTER TABLE IF EXISTS stories ADD COLUMN IF NOT EXISTS font_style VARCHAR(50);

-- Migration: dislike_count manquant sur comments et reels
ALTER TABLE IF EXISTS comments ADD COLUMN IF NOT EXISTS dislike_count INTEGER DEFAULT 0;
ALTER TABLE IF EXISTS reels ADD COLUMN IF NOT EXISTS dislike_count INTEGER DEFAULT 0;

-- Migration: colonnes concert/event manquantes dans comments
ALTER TABLE IF EXISTS comments ADD COLUMN IF NOT EXISTS concert_id UUID REFERENCES concerts(id) ON DELETE CASCADE;
ALTER TABLE IF EXISTS comments ADD COLUMN IF NOT EXISTS event_id UUID REFERENCES events(id) ON DELETE CASCADE;

-- Report les tables créées
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public' ORDER BY table_name;
