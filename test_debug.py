# -*- coding: utf-8 -*-
from nlp_parser import parse_sentence
from datetime import datetime

print("=" * 70)
print("TEST 10: Thứ 5 tuần sau")
print("=" * 70)
print(f"Hôm nay: {datetime.now().strftime('%Y-%m-%d (%A)')}")
print()

test_cases = [
    "Họp với sếp 9h sáng thứ 5 tuần sau",
    "Họp với sếp 9h sáng thứ 5 tuần tới",
    "Họp với sếp 9h sáng thứ 5 tới",
    "Họp với sếp 9h sáng mai",
]

for test in test_cases:
    result = parse_sentence(test)
    print(f"Câu: {test}")
    if "error" in result:
        print(f"  LỖI: {result['error']}")
    else:
        print(f"  Event: {result['event']}")
        print(f"  Time: {result['start_time']}")
        print(f"  Location: {result['location']}")
        print(f"  Reminder: {result['reminder_minutes']}")
    print()

print("Expected for '9h sáng thứ 5 tuần sau': 2025-11-20T09:00:00")
