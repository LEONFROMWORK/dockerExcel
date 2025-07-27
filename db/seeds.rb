# Database seeds for Excel Unified application

puts "🌱 Seeding database..."

# Create demo users
demo_users = [
  {
    email: 'admin@excel-unified.com',
    password: 'password123',
    name: 'Admin User',
    avatar_url: 'https://ui-avatars.com/api/?name=Admin+User'
  },
  {
    email: 'demo@excel-unified.com',
    password: 'password123',
    name: 'Demo User',
    avatar_url: 'https://ui-avatars.com/api/?name=Demo+User'
  }
]

demo_users.each do |user_data|
  user = User.find_or_create_by(email: user_data[:email]) do |u|
    u.password = user_data[:password]
    u.name = user_data[:name]
    u.avatar_url = user_data[:avatar_url]
  end
  puts "✅ Created user: #{user.email}"
end

# Create knowledge base Q&A pairs
qa_pairs = [
  {
    question: "Excel에서 #DIV/0! 오류는 무엇인가요?",
    answer: "#DIV/0! 오류는 0으로 나누기를 시도할 때 발생합니다. 예를 들어 =A1/B1에서 B1이 0이거나 비어있을 때 이 오류가 나타납니다. IFERROR 함수를 사용하여 처리할 수 있습니다.",
    category: "errors",
    tags: ["오류", "나누기", "수식"]
  },
  {
    question: "Excel에서 #N/A 오류는 어떻게 해결하나요?",
    answer: "#N/A 오류는 주로 VLOOKUP, MATCH 등의 함수가 찾는 값을 발견하지 못할 때 발생합니다. 찾는 값이 존재하는지 확인하고, IFNA 함수로 오류를 처리할 수 있습니다.",
    category: "errors",
    tags: ["오류", "VLOOKUP", "검색"]
  },
  {
    question: "Excel에서 #NAME? 오류의 원인은 무엇인가요?",
    answer: "#NAME? 오류는 Excel이 수식의 텍스트를 인식하지 못할 때 발생합니다. 함수명 오타, 정의되지 않은 이름 참조, 텍스트에 따옴표 누락 등이 주요 원인입니다.",
    category: "errors",
    tags: ["오류", "함수명", "구문"]
  },
  {
    question: "VLOOKUP과 XLOOKUP의 차이점은 무엇인가요?",
    answer: "XLOOKUP은 VLOOKUP의 개선된 버전으로, 왼쪽 조회 가능, 기본값 설정, 배열 반환, 정확히 일치/근사치 선택 등의 장점이 있습니다. Excel 365에서 사용 가능합니다.",
    category: "functions",
    tags: ["함수", "검색", "VLOOKUP", "XLOOKUP"]
  },
  {
    question: "Excel에서 조건부 서식을 어떻게 적용하나요?",
    answer: "홈 탭 > 조건부 서식에서 규칙을 선택합니다. 셀 값, 수식, 데이터 막대, 색 눈금 등 다양한 옵션을 사용할 수 있으며, 새 규칙으로 사용자 정의도 가능합니다.",
    category: "formatting",
    tags: ["서식", "조건부", "시각화"]
  },
  {
    question: "피벗 테이블은 어떻게 만드나요?",
    answer: "데이터 범위 선택 > 삽입 > 피벗 테이블을 클릭합니다. 행, 열, 값 영역에 필드를 배치하여 데이터를 요약하고 분석할 수 있습니다.",
    category: "analysis",
    tags: ["피벗", "분석", "요약"]
  },
  {
    question: "Excel에서 매크로를 기록하는 방법은?",
    answer: "개발 도구 탭 > 매크로 기록을 클릭합니다. 작업을 수행한 후 기록 중지를 누르면 VBA 코드가 생성됩니다. 보안 설정에서 매크로를 활성화해야 합니다.",
    category: "vba",
    tags: ["매크로", "VBA", "자동화"]
  },
  {
    question: "배열 수식은 어떻게 입력하나요?",
    answer: "Excel 365에서는 일반 Enter로 입력 가능하지만, 이전 버전에서는 Ctrl+Shift+Enter를 눌러야 합니다. 중괄호 {}가 자동으로 추가됩니다.",
    category: "formulas",
    tags: ["배열", "수식", "단축키"]
  },
  {
    question: "Excel 파일 크기를 줄이는 방법은?",
    answer: "불필요한 서식 제거, 이미지 압축, 숨겨진 시트 삭제, 외부 링크 제거, .xlsb 형식으로 저장 등의 방법으로 파일 크기를 줄일 수 있습니다.",
    category: "optimization",
    tags: ["최적화", "파일크기", "성능"]
  },
  {
    question: "Power Query는 무엇인가요?",
    answer: "Power Query는 데이터를 가져오고, 변환하고, 결합하는 도구입니다. 데이터 탭에서 접근 가능하며, M 언어로 고급 변환도 가능합니다.",
    category: "data",
    tags: ["PowerQuery", "데이터", "ETL"]
  }
]

qa_pairs.each do |qa|
  KnowledgeQaPair.find_or_create_by(question: qa[:question]) do |pair|
    pair.answer = qa[:answer]
    pair.category = qa[:category]
    pair.tags = qa[:tags]
    pair.relevance_score = rand(0.8..1.0)
  end
end

puts "✅ Created #{qa_pairs.length} knowledge base Q&A pairs"

# Create sample Excel file records
admin_user = User.find_by(email: 'admin@excel-unified.com')

sample_files = [
  {
    filename: 'sales_report_2024.xlsx',
    file_type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    file_size: 1024 * 512, # 512KB
    status: 'completed',
    metadata: {
      sheets: ['Summary', 'Q1', 'Q2', 'Q3', 'Q4'],
      rows: 5000,
      columns: 20
    }
  },
  {
    filename: 'budget_template.xlsx',
    file_type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    file_size: 1024 * 256, # 256KB
    status: 'completed',
    metadata: {
      sheets: ['Budget', 'Forecast', 'Actuals'],
      rows: 1000,
      columns: 15
    }
  },
  {
    filename: 'inventory_tracking.xlsx',
    file_type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    file_size: 1024 * 1024, # 1MB
    status: 'pending',
    metadata: {
      sheets: ['Products', 'Suppliers', 'Orders'],
      rows: 10000,
      columns: 25
    }
  }
]

sample_files.each do |file_data|
  excel_file = admin_user.excel_files.find_or_create_by(filename: file_data[:filename]) do |f|
    f.file_type = file_data[:file_type]
    f.file_size = file_data[:file_size]
    f.status = file_data[:status]
    f.metadata = file_data[:metadata]
    f.analyzed_at = Time.current if file_data[:status] == 'completed'
  end
  
  # Add sample error detections for completed files
  if excel_file.status == 'completed'
    errors = [
      {
        error_type: 'formula_error',
        sheet_name: excel_file.metadata['sheets'].first,
        cell_reference: 'B10',
        severity: 'high',
        description: '#DIV/0! error in formula',
        is_auto_fixable: true
      },
      {
        error_type: 'data_quality',
        sheet_name: excel_file.metadata['sheets'].first,
        cell_reference: 'A5:A10',
        severity: 'medium',
        description: 'Duplicate values detected',
        is_auto_fixable: false
      }
    ]
    
    errors.each do |error|
      excel_file.error_detections.find_or_create_by(
        error_type: error[:error_type],
        cell_reference: error[:cell_reference]
      ) do |e|
        e.sheet_name = error[:sheet_name]
        e.severity = error[:severity]
        e.description = error[:description]
        e.is_auto_fixable = error[:is_auto_fixable]
      end
    end
  end
  
  puts "✅ Created Excel file: #{excel_file.filename}"
end

# Create user preferences
User.all.each do |user|
  UserPreference.find_or_create_by(user: user) do |pref|
    pref.ui_settings = {
      theme: 'light',
      sidebar_collapsed: false,
      default_view: 'dashboard'
    }
    pref.notification_settings = {
      email_enabled: true,
      analysis_complete: true,
      error_detected: true
    }
    pref.analysis_settings = {
      auto_fix_enabled: true,
      vba_analysis_enabled: true,
      ocr_enabled: true
    }
  end
end

puts "✅ Created user preferences"

puts "🎉 Database seeding completed!"