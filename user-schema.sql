CREATE OR REPLACE FUNCTION set_updated_at() RETURNS TRIGGER AS $function$
BEGIN
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$function$ LANGUAGE plpgsql;

CREATE TABLE IF NOT EXISTS author_info (
    author_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_author_name UNIQUE (first_name, last_name)
);

CREATE TRIGGER trigger_author_info_updated
BEFORE UPDATE ON author_info
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS book_info (
    book_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    book_isbn VARCHAR(20) UNIQUE,
    internal_code VARCHAR(50) UNIQUE,
    book_title VARCHAR(255) NOT NULL,
    publish_date DATE,
    publisher VARCHAR(255),
    edition VARCHAR(50),
    issue_number VARCHAR(50) DEFAULT NULL,
    volume_number INT DEFAULT NULL,
    page_amount INT DEFAULT NULL,
    book_description TEXT,
    language VARCHAR(10),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    search_vector tsvector GENERATED ALWAYS AS (
        to_tsvector('english', COALESCE(book_title, '') || ' ' || COALESCE(book_description, ''))
    ) STORED,
    CONSTRAINT chk_has_identifier CHECK (book_isbn IS NOT NULL OR internal_code IS NOT NULL)
);

CREATE INDEX idx_book_info_search ON book_info USING GIN (search_vector);

CREATE TRIGGER trigger_book_info_updated
BEFORE UPDATE ON book_info
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS creator_role_type (
    creator_role_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    creator_role_name public.citext UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS book_author (
    book_id INT REFERENCES book_info(book_id) ON DELETE CASCADE,
    author_id INT REFERENCES author_info(author_id) ON DELETE CASCADE,
    creator_role_id INT NOT NULL REFERENCES creator_role_type(creator_role_id) ON DELETE RESTRICT,
    PRIMARY KEY (book_id, author_id, creator_role_id)
);

CREATE TABLE IF NOT EXISTS genre (
    genre_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    genre_name public.citext UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS book_genre (
    book_id INT REFERENCES book_info(book_id) ON DELETE CASCADE,
    genre_id INT REFERENCES genre(genre_id) ON DELETE CASCADE,
    PRIMARY KEY (book_id, genre_id)
);

CREATE TABLE IF NOT EXISTS media_type (
    media_type_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    media_type_name public.citext UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS book_media_type (
    book_id INT REFERENCES book_info(book_id) ON DELETE CASCADE,
    media_type_id INT REFERENCES media_type(media_type_id) ON DELETE CASCADE,
    PRIMARY KEY (book_id, media_type_id)
);

CREATE TABLE IF NOT EXISTS book_adaptation (
    adaptation_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    book_id INT NOT NULL REFERENCES book_info(book_id) ON DELETE CASCADE,
    adaptation_type VARCHAR(50) NOT NULL CHECK (adaptation_type IN (
        'Feature Film', 'Television Series', 'Stage Play', 'Radio Drama', 'Video Game'
    )),
    title VARCHAR(255) NOT NULL,
    release_date DATE
);

CREATE TABLE IF NOT EXISTS game_info (
    game_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    game_title VARCHAR(255) UNIQUE NOT NULL,
    publisher VARCHAR(255),
    release_date DATE,
    min_players INT CHECK (min_players > 0),
    max_players INT CHECK (max_players >= min_players),
    play_time_minutes INT,
    min_age INT,
    game_description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TRIGGER trigger_game_info_updated
BEFORE UPDATE ON game_info
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS designer_info (
    designer_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_designer_name UNIQUE (first_name, last_name)
);

CREATE TRIGGER trigger_designer_info_updated
BEFORE UPDATE ON designer_info
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS game_designer (
    game_id INT REFERENCES game_info(game_id) ON DELETE CASCADE,
    designer_id INT REFERENCES designer_info(designer_id) ON DELETE CASCADE,
    PRIMARY KEY (game_id, designer_id)
);

CREATE TABLE IF NOT EXISTS game_genre (
    game_id INT REFERENCES game_info(game_id) ON DELETE CASCADE,
    genre_id INT REFERENCES genre(genre_id) ON DELETE CASCADE,
    PRIMARY KEY (game_id, genre_id)
);

CREATE TABLE IF NOT EXISTS book_tracking (
    user_id INT NOT NULL,
    book_id INT REFERENCES book_info(book_id) ON DELETE CASCADE,
    book_summary VARCHAR(300),
    book_ratings INT CHECK (book_ratings BETWEEN 1 AND 5),
    read_status VARCHAR(10) NOT NULL DEFAULT 'want' CHECK (read_status IN ('want', 'reading', 'finished')),
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, book_id)
);

CREATE TRIGGER trigger_book_tracking_updated
BEFORE UPDATE ON book_tracking
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS reading_progress (
    progress_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id INT NOT NULL,
    book_id INT NOT NULL,
    progress_percent NUMERIC(5,2) CHECK (progress_percent BETWEEN 0 AND 100),
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FOREIGN KEY (user_id, book_id) REFERENCES book_tracking(user_id, book_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS game_tracking (
    user_id INT NOT NULL,
    game_id INT REFERENCES game_info(game_id) ON DELETE CASCADE,
    game_notes TEXT,
    game_ratings INT CHECK (game_ratings BETWEEN 1 AND 5),
    play_status VARCHAR(10) NOT NULL DEFAULT 'want' CHECK (play_status IN ('want', 'owned', 'played')),
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, game_id)
);

CREATE TRIGGER trigger_game_tracking_updated
BEFORE UPDATE ON game_tracking
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE INDEX IF NOT EXISTS index_reading_progress_user_book ON reading_progress(user_id, book_id);
CREATE INDEX IF NOT EXISTS index_book_adaptation_book_id ON book_adaptation(book_id);
CREATE INDEX IF NOT EXISTS index_book_author_author_id ON book_author(author_id);
CREATE INDEX IF NOT EXISTS index_book_genre_genre_id ON book_genre(genre_id);
CREATE INDEX IF NOT EXISTS index_book_media_type_media_type_id ON book_media_type(media_type_id);
CREATE INDEX IF NOT EXISTS index_book_tracking_book_id ON book_tracking(book_id);
