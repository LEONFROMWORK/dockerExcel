# 테스트 Excel 파일로 오류 감지 테스트
file_path = '/Users/kevin/Downloads/66기초입문-17-엑셀-오류의-모든-것-예제파일.xlsx'

if File.exist?(file_path)
  puts '=== Excel 오류 감지 테스트 시작 ==='

  # 1. Excel 파일을 DB에 저장
  user = User.first || User.create!(
    email: 'test@example.com',
    google_uid: 'test-uid',
    provider: 'google_oauth2',
    name: 'Test User',
    confirmed_at: Time.current
  )

  excel_file = ExcelFile.create!(
    user: user,
    filename: File.basename(file_path),
    file_size: File.size(file_path),
    status: 'pending'
  )

  # 파일을 임시 위치에 복사
  temp_path = Rails.root.join('tmp', "excel_#{excel_file.id}.xlsx")
  FileUtils.cp(file_path, temp_path)

  # 2. Python 서비스를 통한 오류 감지
  puts "\n파일 ID: #{excel_file.id}"
  puts "임시 경로: #{temp_path}"

  client = PythonServiceClient.new
  puts "\nPython 서비스를 통한 오류 감지 중..."

  begin
    result = client.detect_excel_errors(temp_path.to_s, excel_file.id.to_s)

    if result['error']
      puts "❌ 오류 발생: #{result['error']}"
    else
      puts "✅ 감지된 오류 수: #{result['errors'].length}"
      puts "\n오류 목록:"
      result['errors'].each_with_index do |error, i|
        puts "  #{i+1}. [#{error['error_type']}] #{error['location']}: #{error['description']}"
      end

      # 3. 병렬 분석 작업 실행
      puts "\n병렬 분석 작업 실행 중..."
      job = ParallelExcelAnalysisJob.perform_now(excel_file.id)

      # 4. 저장된 분석 결과 확인
      analysis = excel_file.excel_analyses.last
      if analysis
        puts "\n✅ 분석 저장 완료"
        puts "저장된 오류 수: #{analysis.analysis_errors.length}"
        puts "오류 감지 정확도: #{analysis.accuracy}%"
      else
        puts "\n❌ 분석 결과가 저장되지 않았습니다"
      end
    end
  rescue => e
    puts "❌ 예외 발생: #{e.message}"
    puts e.backtrace.first(5).join("\n")
  ensure
    # 임시 파일 정리
    FileUtils.rm_f(temp_path)
  end

  puts "\n=== 테스트 완료 ==="
else
  puts "테스트 파일을 찾을 수 없습니다: #{file_path}"
end
