from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

artifacts_dir = Path('ci-artifacts-17191931415')
results_dir = Path('results')
results_dir.mkdir(exist_ok=True)

files = [artifacts_dir / 'results-3.10.xml', artifacts_dir / 'results-3.11.xml']

summary = []
for f in files:
    if not f.exists():
        print(f"Warning: artifact not found: {f}")
        continue
    # copy to results/
    dest = results_dir / f.name
    shutil.copy2(f, dest)

    root = ET.parse(f).getroot()
    suites = []
    if root.tag == 'testsuites':
        suites = list(root)
    elif root.tag == 'testsuite':
        suites = [root]
    tests = []
    for s in suites:
        for tc in s.findall('testcase'):
            name = tc.get('name')
            classname = tc.get('classname')
            time = tc.get('time')
            status = 'passed'
            if tc.find('failure') is not None:
                status = 'failure'
            elif tc.find('error') is not None:
                status = 'error'
            elif tc.find('skipped') is not None:
                status = 'skipped'
            tests.append((name, classname, status, time))
    summary.append((f.name, len(tests), tests))

print('\nTest artifacts copied to: ' + str(results_dir.resolve()) + '\n')
for fname, count, tests in summary:
    print(f"File: {fname} — {count} test(s)")
    for name, cls, status, time in tests:
        print(f"  - {name} ({cls}) — {status} — {time}s")

# simple totals
total = sum(c for _, c, _ in summary)
print(f"\nTotal tests across artifacts: {total}")
