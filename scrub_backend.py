import re
import sys
import os

def remove_class(filepath, class_name):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    out = []
    in_class = False
    class_indent = 0
    for line in lines:
        match = re.match(r'^(\s*)class ' + class_name + r'\(', line)
        if match:
            in_class = True
            class_indent = len(match.group(1))
            continue
        
        if in_class:
            # check if we exited the class
            if line.strip() != "" and not line.startswith(' ' * (class_indent + 1)):
                in_class = False
            else:
                continue
                
        if not in_class:
            out.append(line)
            
    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(out)

def remove_method(filepath, method_name):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    out = []
    in_method = False
    method_indent = 0
    for line in lines:
        match = re.match(r'^(\s*)def ' + method_name + r'\(', line)
        if match:
            in_method = True
            method_indent = len(match.group(1))
            continue
        
        if in_method:
            if line.strip() != "" and not line.startswith(' ' * (method_indent + 1)):
                in_method = False
            else:
                continue
                
        if not in_method:
            out.append(line)
            
    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(out)

def scrub_journeys():
    models_file = 'backend/core/models.py'
    serializers_file = 'backend/core/serializers.py'
    api_file = 'backend/core/api.py'
    
    # Remove PresetJourney and PresetJourneyStep from models
    remove_class(models_file, 'PresetJourney')
    remove_class(models_file, 'PresetJourneyStep')
    
    # Remove from serializers
    remove_class(serializers_file, 'PresetJourneyStepReadSerializer')
    remove_class(serializers_file, 'PresetJourneyStepWriteSerializer')
    remove_class(serializers_file, 'PresetJourneyReadSerializer')
    remove_class(serializers_file, 'PresetJourneyWriteSerializer')
    
    # Remove from api.py
    remove_class(api_file, 'PresetJourneyViewSet')
    remove_class(api_file, 'PresetJourneyStepViewSet')

def scrub_respondent():
    models_file = 'backend/core/models.py'
    serializers_file = 'backend/core/serializers.py'
    
    # Remove RespondentAlignment choices
    remove_class(models_file, 'RespondentAlignment')
    
    # Remove _strip_respondent_protected_fields
    remove_method(serializers_file, '_strip_respondent_protected_fields')

if __name__ == '__main__':
    scrub_journeys()
    scrub_respondent()
    print("Scrubbed successfully.")
