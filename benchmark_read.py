import subprocess
import re
import statistics
import sys

TRIALS = 100

COMMAND = ['./hlmod-hl/build/bin/hl', 'deadcells.exe']


def run_benchmark(command, num_trials):
    read_times = []
    
    time_regex = re.compile(r"Code read took ([\d\.]+) μs\.")

    print(f"Starting benchmark...")
    print(f"Command: {' '.join(command)}")
    print(f"Number of Trials: {num_trials}\n")

    for i in range(1, num_trials + 1):
        print(f"--- Running Trial {i}/{num_trials} ---")
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
            )
            
            match = time_regex.search(result.stdout)
            
            if match:
                time_us = float(match.group(1))
                read_times.append(time_us)
                print(f"Success: Found time: {time_us:.2f} μs")
            else:
                print("Warning: Command ran, but could not find code read time in the output.")

        except FileNotFoundError:
            print(f"Error: Command not found. Please check the path: {command[0]}", file=sys.stderr)
            return
        except subprocess.CalledProcessError as e:
            print(f"Error: Trial {i} failed with exit code {e.returncode}.", file=sys.stderr)
            print("--- STDOUT ---", file=sys.stderr)
            print(e.stdout, file=sys.stderr)
            print("--- STDERR ---", file=sys.stderr)
            print(e.stderr, file=sys.stderr)
        except Exception as e:
            print(f"An unexpected error occurred: {e}", file=sys.stderr)


    print("\n--- Benchmark Finished ---")

    if not read_times:
        print("No successful trials were recorded. Cannot calculate average.")
        return

    successful_trials = len(read_times)
    average_time = statistics.mean(read_times)
    
    print(f"Successfully recorded {successful_trials}/{num_trials} trials.")
    print(f"\nAverage code read time: {average_time:.2f} μs")
    print(f"Stddev: {statistics.stdev(read_times)} μs")
    print(f"Median: {statistics.median(read_times)} μs")

if __name__ == "__main__":
    run_benchmark(COMMAND, TRIALS)