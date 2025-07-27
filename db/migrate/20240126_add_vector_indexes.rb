class AddVectorIndexes < ActiveRecord::Migration[7.1]
  def up
    # Add vector index for knowledge Q&A pairs
    execute <<-SQL
      CREATE INDEX knowledge_qa_pairs_embedding_idx 
      ON knowledge_qa_pairs 
      USING ivfflat (embedding vector_cosine_ops)
      WITH (lists = 100);
    SQL

    # Add GIN indexes for JSONB columns
    add_index :excel_files, :metadata, using: :gin
    add_index :excel_files, :analysis_results, using: :gin
    add_index :error_detections, :details, using: :gin
    add_index :ai_chat_sessions, :context, using: :gin
    add_index :ai_chat_messages, :metadata, using: :gin
    add_index :knowledge_qa_pairs, :tags, using: :gin
    add_index :excel_comparisons, :comparison_options, using: :gin
    add_index :excel_comparisons, :results, using: :gin
    add_index :formula_analyses, :dependencies, using: :gin
    add_index :formula_analyses, :performance_metrics, using: :gin
    add_index :formula_analyses, :optimization_suggestions, using: :gin
    add_index :vba_analyses, :metrics, using: :gin
    add_index :vba_analyses, :issues, using: :gin
    add_index :vba_analyses, :dependencies, using: :gin
    add_index :vba_analyses, :suggestions, using: :gin
    add_index :activity_logs, :details, using: :gin
    add_index :background_jobs, :parameters, using: :gin
    add_index :background_jobs, :results, using: :gin
    add_index :user_preferences, :ui_settings, using: :gin
    add_index :user_preferences, :notification_settings, using: :gin
    add_index :user_preferences, :analysis_settings, using: :gin
  end

  def down
    # Remove vector index
    execute <<-SQL
      DROP INDEX IF EXISTS knowledge_qa_pairs_embedding_idx;
    SQL

    # Remove GIN indexes
    remove_index :excel_files, :metadata
    remove_index :excel_files, :analysis_results
    remove_index :error_detections, :details
    remove_index :ai_chat_sessions, :context
    remove_index :ai_chat_messages, :metadata
    remove_index :knowledge_qa_pairs, :tags
    remove_index :excel_comparisons, :comparison_options
    remove_index :excel_comparisons, :results
    remove_index :formula_analyses, :dependencies
    remove_index :formula_analyses, :performance_metrics
    remove_index :formula_analyses, :optimization_suggestions
    remove_index :vba_analyses, :metrics
    remove_index :vba_analyses, :issues
    remove_index :vba_analyses, :dependencies
    remove_index :vba_analyses, :suggestions
    remove_index :activity_logs, :details
    remove_index :background_jobs, :parameters
    remove_index :background_jobs, :results
    remove_index :user_preferences, :ui_settings
    remove_index :user_preferences, :notification_settings
    remove_index :user_preferences, :analysis_settings
  end
end