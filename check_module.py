import importlib.util
spec = importlib.util.spec_from_file_location('nlp_parser','f:\\SGU\\ĐỒ ÁN CHUYÊN NGÀNH\\Schedule-Assistant-App\\nlp_parser.py')
mod = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(mod)
    print('Loaded module nlp_parser')
    print('Has extract_time_info:', hasattr(mod,'extract_time_info'))
    print('extract_time_info at:', getattr(mod,'extract_time_info',None))
    print('Has parse_sentence:', hasattr(mod,'parse_sentence'))
except Exception as e:
    print('Import error:', e)
