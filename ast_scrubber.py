import ast
import sys

def remove_ast_nodes(filepath, class_names, method_names=None, field_names=None):
    with open(filepath, 'r', encoding='utf-8') as f:
        source = f.read()
    
    tree = ast.parse(source)
    lines_to_remove = set()
    
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            if node.name in class_names:
                start = node.lineno
                if node.decorator_list:
                    start = min(d.lineno for d in node.decorator_list)
                for i in range(start, getattr(node, 'end_lineno', node.lineno) + 1):
                    lines_to_remove.add(i)
            else:
                for child in ast.iter_child_nodes(node):
                    if isinstance(child, ast.FunctionDef) and method_names and child.name in method_names:
                        start = child.lineno
                        if child.decorator_list:
                            start = min(d.lineno for d in child.decorator_list)
                        for i in range(start, getattr(child, 'end_lineno', child.lineno) + 1):
                            lines_to_remove.add(i)
                    elif isinstance(child, ast.Assign) and field_names:
                        for target in child.targets:
                            if isinstance(target, ast.Name) and target.id in field_names:
                                for i in range(child.lineno, getattr(child, 'end_lineno', child.lineno) + 1):
                                    lines_to_remove.add(i)
                                    
        elif isinstance(node, ast.FunctionDef) and method_names and node.name in method_names:
            start = node.lineno
            if node.decorator_list:
                start = min(d.lineno for d in node.decorator_list)
            for i in range(start, getattr(node, 'end_lineno', node.lineno) + 1):
                lines_to_remove.add(i)

    lines = source.split('\n')
    out_lines = []
    for i, line in enumerate(lines):
        if (i + 1) not in lines_to_remove:
            out_lines.append(line)
            
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out_lines))

if __name__ == '__main__':
    # 1. Models
    remove_ast_nodes(
        'backend/core/models.py', 
        ['PresetJourney', 'PresetJourneyStep', 'RespondentAlignment'],
        field_names=['respondent_alignment']
    )
    
    # 2. Serializers
    remove_ast_nodes(
        'backend/core/serializers.py', 
        [
            'PresetJourneyStepReadSerializer', 'PresetJourneyStepWriteSerializer',
            'PresetJourneyReadSerializer', 'PresetJourneyWriteSerializer'
        ],
        ['_strip_respondent_protected_fields']
    )
    
    print("AST-based scrub successful!")
