"""
Performance benchmark for VBA Analyzer
"""

import asyncio
import time
import statistics
import os
import sys
import tempfile
import zipfile

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.services.advanced_vba_analyzer import AdvancedVBAAnalyzer


class VBAAnalyzerBenchmark:
    """Benchmark suite for VBA Analyzer performance"""

    def __init__(self):
        self.analyzer = AdvancedVBAAnalyzer()
        self.results = []

    def create_test_excel_with_vba(
        self, num_modules: int, lines_per_module: int
    ) -> str:
        """Create a test Excel file with VBA modules"""
        temp_file = tempfile.NamedTemporaryFile(suffix=".xlsm", delete=False)

        # Create a simple Excel structure (this is a simplified version)
        # In real scenario, we'd use openpyxl or similar
        with zipfile.ZipFile(temp_file.name, "w") as zf:
            # Add basic Excel structure
            zf.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types/>')

            # Simulate VBA project
            vba_content = self._generate_vba_content(num_modules, lines_per_module)
            zf.writestr("xl/vbaProject.bin", vba_content.encode())

        return temp_file.name

    def _generate_vba_content(self, num_modules: int, lines_per_module: int) -> str:
        """Generate sample VBA content with various error patterns"""
        vba_code = ""

        for module_num in range(num_modules):
            vba_code += f"\n'=== Module{module_num + 1} ===\n"
            vba_code += "Option Explicit\n\n"

            # Add various patterns that will trigger detection
            patterns = [
                'Sub TestError{i}()\n    Worksheets("Sheet{i}").Range("A1").Value = {i}\nEnd Sub\n',
                "Function Calculate{i}()\n    Dim result As Integer\n    result = {i} * 2\n    Calculate{i} = result\nEnd Function\n",
                'Sub PerformanceTest{i}()\n    Sheets("Sheet1").Select\n    Range("A{i}").Select\nEnd Sub\n',
                "Sub LoopTest{i}()\n    Dim i As Integer\n    For i = 1 To {i}\n        Cells(i, 1).Value = i\n    Next i\nEnd Sub\n",
            ]

            for i in range(lines_per_module // 10):
                pattern = patterns[i % len(patterns)]
                vba_code += pattern.format(i=i + 1)

        return vba_code

    async def benchmark_file_sizes(self):
        """Benchmark different file sizes"""
        print("\n=== File Size Benchmark ===")

        test_configs = [
            (1, 100),  # Small: 1 module, 100 lines
            (5, 200),  # Medium: 5 modules, 200 lines each
            (10, 500),  # Large: 10 modules, 500 lines each
            (20, 1000),  # XLarge: 20 modules, 1000 lines each
        ]

        for num_modules, lines_per_module in test_configs:
            file_path = self.create_test_excel_with_vba(num_modules, lines_per_module)

            try:
                # Run multiple iterations
                times = []
                for _ in range(3):
                    start_time = time.time()
                    result = await self.analyzer.analyze_file(file_path)
                    end_time = time.time()

                    elapsed = end_time - start_time
                    times.append(elapsed)

                avg_time = statistics.mean(times)
                std_dev = statistics.stdev(times) if len(times) > 1 else 0

                print(f"\nModules: {num_modules}, Lines/Module: {lines_per_module}")
                print(f"Average Time: {avg_time:.3f}s (±{std_dev:.3f}s)")
                print(
                    f"Errors Found: {result.get('summary', {}).get('total_errors', 0)}"
                )

                self.results.append(
                    {
                        "modules": num_modules,
                        "lines_per_module": lines_per_module,
                        "avg_time": avg_time,
                        "errors_found": result.get("summary", {}).get(
                            "total_errors", 0
                        ),
                    }
                )

            finally:
                os.unlink(file_path)

    async def benchmark_error_detection(self):
        """Benchmark error detection patterns"""
        print("\n=== Error Detection Benchmark ===")

        # Create file with known error patterns
        test_code = """
Option Explicit

Sub TestAllErrorPatterns()
    ' Runtime Error 1004
    Worksheets("NonExistent").Range("A1").Value = "Test"

    ' Runtime Error 91
    Dim ws As Worksheet
    Set ws = Nothing
    ws.Range("A1").Value = "Test"

    ' Runtime Error 13
    Dim num As Integer
    num = "abc" + 123

    ' Security risks
    Shell "cmd.exe /c dir"
    CreateObject("WScript.Shell").Run "notepad.exe"
    CreateObject("Scripting.FileSystemObject").CreateTextFile("C:\\test.txt")

    ' Performance issues
    Sheets("Sheet1").Select
    Range("A1").Select
    Selection.Value = "Test"

    ' Triple nested loops
    Dim i As Integer, j As Integer, k As Integer
    For i = 1 To 10
        For j = 1 To 10
            For k = 1 To 10
                ' Performance killer
            Next k
        Next j
    Next i

    ' Obfuscation patterns
    Dim s As String
    s = Chr(72) & Chr(101) & Chr(108) & Chr(108) & Chr(111)
    s = StrReverse("dlroW olleH")
End Sub

' Missing error handling
Sub DivisionByZero()
    Dim result As Double
    result = 10 / 0
End Sub
"""

        # Create test file
        temp_file = tempfile.NamedTemporaryFile(suffix=".xlsm", delete=False)
        with zipfile.ZipFile(temp_file.name, "w") as zf:
            zf.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types/>')
            zf.writestr("xl/vbaProject.bin", test_code.encode())

        try:
            start_time = time.time()
            result = await self.analyzer.analyze_file(temp_file.name)
            end_time = time.time()

            elapsed = end_time - start_time
            errors = result.get("errors", [])

            print(f"\nDetection Time: {elapsed:.3f}s")
            print(f"Total Errors Found: {len(errors)}")

            # Group errors by category
            by_category = {}
            for error in errors:
                category = error.get("category", "unknown")
                by_category[category] = by_category.get(category, 0) + 1

            print("\nErrors by Category:")
            for category, count in sorted(by_category.items()):
                print(f"  {category}: {count}")

            # Group errors by severity
            by_severity = {}
            for error in errors:
                severity = error.get("severity", "unknown")
                by_severity[severity] = by_severity.get(severity, 0) + 1

            print("\nErrors by Severity:")
            for severity, count in sorted(by_severity.items()):
                print(f"  {severity}: {count}")

        finally:
            os.unlink(temp_file.name)

    async def benchmark_memory_usage(self):
        """Benchmark memory usage"""
        print("\n=== Memory Usage Benchmark ===")

        import psutil
        import gc

        process = psutil.Process()

        # Initial memory
        gc.collect()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Create large file
        file_path = self.create_test_excel_with_vba(50, 2000)

        try:
            # Analyze file
            peak_memory = initial_memory

            async def monitor_memory():
                nonlocal peak_memory
                while True:
                    current_memory = process.memory_info().rss / 1024 / 1024
                    peak_memory = max(peak_memory, current_memory)
                    await asyncio.sleep(0.1)

            # Start memory monitoring
            monitor_task = asyncio.create_task(monitor_memory())

            # Run analysis
            result = await self.analyzer.analyze_file(file_path)

            # Stop monitoring
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass

            # Final memory
            gc.collect()
            final_memory = process.memory_info().rss / 1024 / 1024

            print(f"Initial Memory: {initial_memory:.2f} MB")
            print(f"Peak Memory: {peak_memory:.2f} MB")
            print(f"Final Memory: {final_memory:.2f} MB")
            print(f"Memory Increase: {peak_memory - initial_memory:.2f} MB")

        finally:
            os.unlink(file_path)

    def print_summary(self):
        """Print benchmark summary"""
        print("\n=== BENCHMARK SUMMARY ===")

        if self.results:
            print("\nPerformance by File Size:")
            print("-" * 60)
            print(f"{'Modules':<10} {'Lines/Mod':<12} {'Avg Time':<12} {'Errors':<10}")
            print("-" * 60)

            for result in self.results:
                print(
                    f"{result['modules']:<10} {result['lines_per_module']:<12} "
                    f"{result['avg_time']:<12.3f} {result['errors_found']:<10}"
                )

            # Calculate throughput
            print("\nThroughput Analysis:")
            for result in self.results:
                total_lines = result["modules"] * result["lines_per_module"]
                lines_per_second = total_lines / result["avg_time"]
                print(f"  {total_lines:6} lines: {lines_per_second:8.0f} lines/second")


async def main():
    """Run all benchmarks"""
    benchmark = VBAAnalyzerBenchmark()

    print("VBA Analyzer Performance Benchmark")
    print("=" * 60)

    # Run benchmarks
    await benchmark.benchmark_file_sizes()
    await benchmark.benchmark_error_detection()

    try:
        await benchmark.benchmark_memory_usage()
    except ImportError:
        print("\n[Skipping memory benchmark - psutil not installed]")

    # Print summary
    benchmark.print_summary()

    print("\n✅ Benchmark complete!")


if __name__ == "__main__":
    asyncio.run(main())
