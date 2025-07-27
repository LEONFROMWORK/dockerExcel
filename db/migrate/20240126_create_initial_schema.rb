class CreateInitialSchema < ActiveRecord::Migration[7.1]
  def change
    # Enable pgvector extension
    enable_extension 'pgvector' unless extension_enabled?('pgvector')

    # Users table (managed by Devise)
    create_table :users do |t|
      t.string :email, null: false, default: ""
      t.string :encrypted_password, null: false, default: ""
      t.string :reset_password_token
      t.datetime :reset_password_sent_at
      t.datetime :remember_created_at
      t.integer :sign_in_count, default: 0, null: false
      t.datetime :current_sign_in_at
      t.datetime :last_sign_in_at
      t.inet :current_sign_in_ip
      t.inet :last_sign_in_ip
      t.string :provider
      t.string :uid
      t.string :name
      t.string :avatar_url
      t.timestamps
    end

    add_index :users, :email, unique: true
    add_index :users, :reset_password_token, unique: true
    add_index :users, [:provider, :uid], unique: true

    # Excel files table
    create_table :excel_files do |t|
      t.references :user, foreign_key: true
      t.string :filename, null: false
      t.string :file_path
      t.string :file_type
      t.integer :file_size
      t.string :status, default: 'pending'
      t.jsonb :metadata, default: {}
      t.jsonb :analysis_results, default: {}
      t.datetime :analyzed_at
      t.timestamps
    end

    add_index :excel_files, :status
    add_index :excel_files, :created_at

    # Error detections table
    create_table :error_detections do |t|
      t.references :excel_file, foreign_key: true
      t.string :error_type, null: false
      t.string :sheet_name
      t.string :cell_reference
      t.string :severity
      t.text :description
      t.jsonb :details, default: {}
      t.boolean :is_auto_fixable, default: false
      t.string :fix_status, default: 'pending'
      t.text :fix_applied
      t.datetime :fixed_at
      t.timestamps
    end

    add_index :error_detections, :error_type
    add_index :error_detections, :severity
    add_index :error_detections, :fix_status

    # AI chat sessions table
    create_table :ai_chat_sessions do |t|
      t.references :user, foreign_key: true
      t.references :excel_file, foreign_key: true
      t.string :session_id, null: false
      t.string :status, default: 'active'
      t.jsonb :context, default: {}
      t.datetime :started_at
      t.datetime :ended_at
      t.timestamps
    end

    add_index :ai_chat_sessions, :session_id, unique: true
    add_index :ai_chat_sessions, :status

    # AI chat messages table
    create_table :ai_chat_messages do |t|
      t.references :ai_chat_session, foreign_key: true
      t.string :role, null: false # 'user' or 'assistant'
      t.text :content
      t.jsonb :metadata, default: {}
      t.timestamps
    end

    add_index :ai_chat_messages, :created_at

    # Knowledge base Q&A table
    create_table :knowledge_qa_pairs do |t|
      t.text :question, null: false
      t.text :answer, null: false
      t.string :category
      t.jsonb :tags, default: []
      t.integer :usage_count, default: 0
      t.float :relevance_score
      t.vector :embedding, limit: 1536
      t.timestamps
    end

    add_index :knowledge_qa_pairs, :category
    add_index :knowledge_qa_pairs, :usage_count

    # Excel comparisons table
    create_table :excel_comparisons do |t|
      t.references :user, foreign_key: true
      t.references :expected_file, foreign_key: { to_table: :excel_files }
      t.references :actual_file, foreign_key: { to_table: :excel_files }
      t.string :comparison_type
      t.jsonb :comparison_options, default: {}
      t.jsonb :results, default: {}
      t.string :status, default: 'pending'
      t.datetime :completed_at
      t.timestamps
    end

    add_index :excel_comparisons, :status

    # Formula analyses table
    create_table :formula_analyses do |t|
      t.references :excel_file, foreign_key: true
      t.string :sheet_name
      t.string :cell_reference
      t.text :formula
      t.string :complexity_level
      t.jsonb :dependencies, default: {}
      t.jsonb :performance_metrics, default: {}
      t.jsonb :optimization_suggestions, default: []
      t.timestamps
    end

    add_index :formula_analyses, :complexity_level

    # VBA analyses table
    create_table :vba_analyses do |t|
      t.references :excel_file, foreign_key: true
      t.string :module_name
      t.string :procedure_name
      t.text :code
      t.jsonb :metrics, default: {}
      t.jsonb :issues, default: []
      t.jsonb :dependencies, default: []
      t.jsonb :suggestions, default: []
      t.timestamps
    end

    # Activity logs table
    create_table :activity_logs do |t|
      t.references :user, foreign_key: true
      t.string :action, null: false
      t.string :resource_type
      t.integer :resource_id
      t.jsonb :details, default: {}
      t.inet :ip_address
      t.string :user_agent
      t.timestamps
    end

    add_index :activity_logs, [:resource_type, :resource_id]
    add_index :activity_logs, :action
    add_index :activity_logs, :created_at

    # Background jobs tracking table
    create_table :background_jobs do |t|
      t.string :job_id, null: false
      t.string :job_type, null: false
      t.references :user, foreign_key: true
      t.string :status, default: 'queued'
      t.jsonb :parameters, default: {}
      t.jsonb :results, default: {}
      t.text :error_message
      t.datetime :started_at
      t.datetime :completed_at
      t.integer :retry_count, default: 0
      t.timestamps
    end

    add_index :background_jobs, :job_id, unique: true
    add_index :background_jobs, :status
    add_index :background_jobs, :job_type

    # User preferences table
    create_table :user_preferences do |t|
      t.references :user, foreign_key: true
      t.jsonb :ui_settings, default: {}
      t.jsonb :notification_settings, default: {}
      t.jsonb :analysis_settings, default: {}
      t.string :preferred_language, default: 'ko'
      t.string :timezone, default: 'Asia/Seoul'
      t.timestamps
    end
  end
end