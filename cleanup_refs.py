import re
import os

files = [
    'backend/core/models.py',
    'backend/sec_intel/models.py',
    'backend/core/startup.py',
    'backend/core/preset_editor.py',
    'backend/core/api.py',
    'backend/core/urls.py',
    'backend/app_tests/api/test_api_requirement_assessments.py',
    'backend/core/serializers.py',
]

for fpath in files:
    if not os.path.exists(fpath): continue
    with open(fpath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Very crude cleanup of dangling references
    content = re.sub(r'PresetJourneyStepViewSet,?', '', content)
    content = re.sub(r'PresetJourneyViewSet,?', '', content)
    content = re.sub(r'PresetJourneyStepReadSerializer,?', '', content)
    content = re.sub(r'PresetJourneyStepWriteSerializer,?', '', content)
    content = re.sub(r'PresetJourneyReadSerializer,?', '', content)
    content = re.sub(r'PresetJourneyWriteSerializer,?', '', content)
    content = re.sub(r'PresetJourneyStep,?', '', content)
    content = re.sub(r'PresetJourney,?', '', content)
    content = re.sub(r'RespondentAlignment\.choices,?', '[],', content)
    content = re.sub(r'RespondentAlignment\.choices', '[]', content)
    content = re.sub(r'RespondentAlignment,?', '', content)
    
    # Remove URLs for journeys
    content = re.sub(r'router\.register\(r"journeys".*?\)\n?', '', content)
    content = re.sub(r'router\.register\(r"journey-steps".*?\)\n?', '', content)
    
    with open(fpath, 'w', encoding='utf-8') as f:
        f.write(content)
print("Cleaned dangling references.")
