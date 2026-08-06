#!/usr/bin/env python3
"""
Script to remove old function definitions from cli.py after refactoring.
"""

def remove_old_functions():
    """Remove old web_search, news_search, and helper functions from cli.py"""
    
    with open('scout_it/cli.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Find line numbers for functions to remove
    removals = []
    
    # Find _ERROR_PAGE_PHRASES
    for i, line in enumerate(lines):
        if line.strip().startswith('_ERROR_PAGE_PHRASES = ['):
            # Find the end (closing ])
            for j in range(i, min(i+20, len(lines))):
                if ']' in lines[j]:
                    removals.append(('_ERROR_PAGE_PHRASES', i, j+1))
                    break
            break
    
    # Find function definitions
    i = 0
    while i < len(lines):
        line = lines[i]
        
        if line.startswith('def web_search('):
            # Find end of function (next def at column 0 or end of file)
            start = i
            i += 1
            while i < len(lines) and not (lines[i].startswith('def ') and lines[i][0] == 'd'):
                i += 1
            removals.append(('web_search', start, i))
            continue
            
        elif line.startswith('def news_search('):
            start = i
            i += 1
            while i < len(lines) and not (lines[i].startswith('def ') and lines[i][0] == 'd'):
                i += 1
            removals.append(('news_search', start, i))
            continue
            
        elif line.startswith('def _extract_news_content('):
            start = i
            i += 1
            while i < len(lines) and not (lines[i].startswith('def ') and lines[i][0] == 'd'):
                i += 1
            removals.append(('_extract_news_content', start, i))
            continue
            
        elif line.startswith('def _extract_meta_description('):
            start = i
            i += 1
            while i < len(lines) and not (lines[i].startswith('def ') and lines[i][0] == 'd'):
                i += 1
            removals.append(('_extract_meta_description', start, i))
            continue
        
        i += 1
    
    # Sort removals by start line (in reverse to remove from bottom up)
    removals.sort(key=lambda x: x[1], reverse=True)
    
    print("Functions to remove:")
    for name, start, end in removals:
        print(f"  {name}: lines {start+1}-{end} ({end-start} lines)")
    
    # Remove the lines (from bottom to top to preserve line numbers)
    new_lines = lines[:]
    for name, start, end in removals:
        # Add a comment explaining what was removed
        comment = f"\n# ═══════════════════════════════════════════════════════════════════════════════\n"
        comment += f"# {name} has been moved to scout_it/{name.replace('_', '-')}/\n"
        comment += f"# It is imported at the top of this file via importlib\n"
        comment += f"# ═══════════════════════════════════════════════════════════════════════════════\n\n"
        
        # Replace the function with the comment
        new_lines[start:end] = [comment]
    
    # Write back
    with open('scout_it/cli.py', 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    
    original_count = len(lines)
    new_count = len(new_lines)
    removed_count = original_count - new_count
    
    print(f"\n✅ Removed {removed_count} lines from cli.py")
    print(f"   Original: {original_count} lines")
    print(f"   New: {new_count} lines")
    print(f"   Reduction: {removed_count} lines ({removed_count/original_count*100:.1f}%)")

if __name__ == '__main__':
    remove_old_functions()
