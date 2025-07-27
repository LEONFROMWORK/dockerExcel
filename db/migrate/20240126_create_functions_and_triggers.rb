class CreateFunctionsAndTriggers < ActiveRecord::Migration[7.1]
  def up
    # Function to update updated_at timestamp
    execute <<-SQL
      CREATE OR REPLACE FUNCTION update_updated_at_column()
      RETURNS TRIGGER AS $$
      BEGIN
        NEW.updated_at = CURRENT_TIMESTAMP;
        RETURN NEW;
      END;
      $$ language 'plpgsql';
    SQL

    # Function to calculate similarity score
    execute <<-SQL
      CREATE OR REPLACE FUNCTION calculate_similarity(
        embedding1 vector(1536),
        embedding2 vector(1536)
      )
      RETURNS float AS $$
      BEGIN
        RETURN 1 - (embedding1 <=> embedding2);
      END;
      $$ language 'plpgsql' IMMUTABLE;
    SQL

    # Function to search similar Q&A pairs
    execute <<-SQL
      CREATE OR REPLACE FUNCTION search_similar_qa(
        query_embedding vector(1536),
        match_threshold float DEFAULT 0.7,
        match_count int DEFAULT 5
      )
      RETURNS TABLE(
        id bigint,
        question text,
        answer text,
        category varchar,
        similarity float
      ) AS $$
      BEGIN
        RETURN QUERY
        SELECT
          kq.id,
          kq.question,
          kq.answer,
          kq.category,
          calculate_similarity(kq.embedding, query_embedding) as similarity
        FROM knowledge_qa_pairs kq
        WHERE calculate_similarity(kq.embedding, query_embedding) > match_threshold
        ORDER BY similarity DESC
        LIMIT match_count;
      END;
      $$ language 'plpgsql' STABLE;
    SQL

    # Function to log activity
    execute <<-SQL
      CREATE OR REPLACE FUNCTION log_activity(
        p_user_id bigint,
        p_action varchar,
        p_resource_type varchar,
        p_resource_id bigint,
        p_details jsonb DEFAULT '{}'::jsonb,
        p_ip_address inet DEFAULT NULL,
        p_user_agent varchar DEFAULT NULL
      )
      RETURNS void AS $$
      BEGIN
        INSERT INTO activity_logs (
          user_id, action, resource_type, resource_id, 
          details, ip_address, user_agent, created_at, updated_at
        )
        VALUES (
          p_user_id, p_action, p_resource_type, p_resource_id,
          p_details, p_ip_address, p_user_agent, NOW(), NOW()
        );
      END;
      $$ language 'plpgsql';
    SQL

    # Function to update Excel file status
    execute <<-SQL
      CREATE OR REPLACE FUNCTION update_excel_file_status()
      RETURNS TRIGGER AS $$
      BEGIN
        IF NEW.status = 'completed' AND OLD.status != 'completed' THEN
          NEW.analyzed_at = CURRENT_TIMESTAMP;
        END IF;
        RETURN NEW;
      END;
      $$ language 'plpgsql';
    SQL

    # Create triggers
    tables_with_updated_at = %w[
      users excel_files error_detections ai_chat_sessions
      ai_chat_messages knowledge_qa_pairs excel_comparisons
      formula_analyses vba_analyses activity_logs
      background_jobs user_preferences
    ]

    tables_with_updated_at.each do |table|
      execute <<-SQL
        CREATE TRIGGER update_#{table}_updated_at
        BEFORE UPDATE ON #{table}
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
      SQL
    end

    # Trigger for Excel file status
    execute <<-SQL
      CREATE TRIGGER update_excel_file_status_trigger
      BEFORE UPDATE ON excel_files
      FOR EACH ROW EXECUTE FUNCTION update_excel_file_status();
    SQL
  end

  def down
    # Drop triggers
    tables_with_updated_at = %w[
      users excel_files error_detections ai_chat_sessions
      ai_chat_messages knowledge_qa_pairs excel_comparisons
      formula_analyses vba_analyses activity_logs
      background_jobs user_preferences
    ]

    tables_with_updated_at.each do |table|
      execute "DROP TRIGGER IF EXISTS update_#{table}_updated_at ON #{table};"
    end

    execute "DROP TRIGGER IF EXISTS update_excel_file_status_trigger ON excel_files;"

    # Drop functions
    execute "DROP FUNCTION IF EXISTS update_updated_at_column();"
    execute "DROP FUNCTION IF EXISTS calculate_similarity(vector, vector);"
    execute "DROP FUNCTION IF EXISTS search_similar_qa(vector, float, int);"
    execute "DROP FUNCTION IF EXISTS log_activity(bigint, varchar, varchar, bigint, jsonb, inet, varchar);"
    execute "DROP FUNCTION IF EXISTS update_excel_file_status();"
  end
end