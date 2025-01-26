import os
import json
from typing import Dict, Any, List
from datetime import datetime
from openai import OpenAI
import re
from rules_analyzer import RulesAnalyzer
from dotenv import load_dotenv

class RulesGenerator:
    # Common regex patterns for all languages
    PATTERNS = {
        'import': {
            'python': r'^(?:from|import)\s+([a-zA-Z0-9_\.]+)',
            'javascript': r'(?:import\s+.*?from\s+[\'"]([^\'\"]+)[\'"]|require\s*\([\'"]([^\'\"]+)[\'"]\))',
            'typescript': r'(?:import|require)\s+.*?[\'"]([^\'\"]+)[\'"]',
            'php': r'namespace\s+([a-zA-Z0-9_\\]+)',
            'csharp': r'using\s+(?:static\s+)?([a-zA-Z0-9_\.]+);',
            'ruby': r'require(?:_relative)?\s+[\'"]([^\'"]+)[\'"]',
            'go': r'import\s+(?:\([^)]*\)|[\'"]([^\'\"]+)[\'"])',
            'cpp': r'#include\s*[<"]([^>"]+)[>"]',
            'c': r'#include\s*[<"]([^>"]+)[>"]',
            'kotlin': r'import\s+([^\n]+)',
            'swift': r'import\s+([^\n]+)',
        },
        'class': {
            'python': r'class\s+(\w+)(?:\((.*?)\))?\s*:',
            'javascript': r'class\s+(\w+)(?:\s+extends\s+(\w+))?\s*{',
            'typescript': r'(?:class|const)\s+(\w+)(?:\s*(?:extends|implements)\s+([^{]+))?(?:\s*=\s*(?:styled|React\.memo|React\.forwardRef))?\s*[{<]',
            'php': r'(?:abstract\s+)?class\s+(\w+)(?:\s+extends\s+(?:\\)?[a-zA-Z0-9_\\]+)?(?:\s+implements\s+(?:\\)?[a-zA-Z0-9_\\]+(?:\s*,\s*(?:\\)?[a-zA-Z0-9_\\]+)*)?',
            'csharp': r'(?:public\s+|private\s+|protected\s+|internal\s+)?(?:abstract\s+)?class\s+(\w+)(?:\s*:\s*([^{]+))?',
            'ruby': r'class\s+(\w+)(?:\s*<\s*(\w+))?',
            'go': r'type\s+(\w+)\s+struct\s*{',
            'cpp': r'(?:class|struct)\s+(\w+)(?:\s*:\s*(?:public|private|protected)\s+(\w+))?(?:\s*{)?',
            'c': r'(?:struct|enum|union)\s+(\w+)(?:\s*{)?',
            'kotlin': r'(?:class|interface|object)\s+(\w+)(?:\s*:\s*([^{]+))?',
            'swift': r'(?:class|struct|protocol|enum)\s+(\w+)(?:\s*:\s*([^{]+))?',
        },
        'function': {
            'python': r'def\s+(\w+)\s*\((.*?)\)(?:\s*->\s*([^:]+))?\s*:',
            'javascript': r'(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=\s*(?:function|\([^)]*\)\s*=>))\s*\((.*?)\)',
            'typescript': r'(?:function|const)\s+(\w+)\s*(?:<[^>]+>)?\s*(?:=\s*)?(?:async\s*)?\((.*?)\)(?:\s*:\s*([^{=]+))?',
            'php': r'(?:public\s+|private\s+|protected\s+)?(?:static\s+)?function\s+(\w+)\s*\([^)]*\)',
            'csharp': r'(?:public|private|protected|internal)?\s*(?:static\s+)?(?:async\s+)?(?:virtual\s+)?(?:<[^>]+>\s+)?(\w+)\s+(\w+)\s*\((.*?)\)',
            'ruby': r'def\s+(?:self\.)?\s*(\w+)(?:\((.*?)\))?',
            'go': r'func\s+(?:\(\w+\s+[^)]+\)\s+)?(\w+)\s*\((.*?)\)(?:\s*\([^)]*\)|[^{]+)?',
            'cpp': r'(?:virtual\s+)?(?:[\w:]+\s+)?(\w+)\s*\((.*?)\)(?:\s*(?:const|override|final|noexcept))?\s*(?:{\s*)?',
            'c': r'(?:static\s+)?(?:[\w*]+\s+)?(\w+)\s*\((.*?)\)(?:\s*{)?',
            'kotlin': r'fun\s+(\w+)\s*\((.*?)\)(?:\s*:\s*([^{]+))?',
            'swift': r'func\s+(\w+)\s*\((.*?)\)(?:\s*->\s*([^{]+))?',
        },
        'method': r'(?:async\s+)?(\w+)\s*\((.*?)\)\s*{',
        'variable': r'(?:const|let|var)\s+(\w+)\s*=\s*([^;]+)',
        'error': r'try\s*{[^}]*}\s*catch\s*\((\w+)\)',
        'interface': r'(?:interface|type)\s+(\w+)(?:\s+extends\s+([^{]+))?',
        'jsx_component': r'<(\w+)(?:\s+[^>]*)?>'
    }

    def __init__(self, project_path: str):
        self.project_path = project_path
        self.analyzer = RulesAnalyzer(project_path)
        
        # Load environment variables from .env
        load_dotenv()
        
        # Initialize OpenAI
        try:
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY is required")

            self.client = OpenAI(
                api_key=api_key,
                base_url="https://api.vsegpt.ru/v1"
            )
            
        except Exception as e:
            print(f"\n⚠️ Error when initializing OpenAI: {e}")
            raise

    def _get_timestamp(self) -> str:
        """Get current timestamp in standard format."""
        return datetime.now().strftime('%B %d, %Y at %I:%M %p')

    def _analyze_project_structure(self) -> Dict[str, Any]:
        """Analyze project structure and collect detailed information."""
        structure = {
            'files': [],
            'dependencies': {},
            'frameworks': [],
            'languages': {},
            'config_files': [],
            'code_contents': {},
            'directory_structure': {},  # Track directory hierarchy
            'language_stats': {},      # Track language statistics by directory
            'patterns': {
                'classes': [],
                'functions': [],
                'imports': [],
                'error_handling': [],
                'configurations': [],
                'naming_patterns': {},
                'code_organization': [],
                'variable_patterns': [],
                'function_patterns': [],
                'class_patterns': [],
                'error_patterns': [],
                'performance_patterns': [],
                'suggest_patterns': [],
                'directory_patterns': []  # Track directory organization patterns
            }
        }

        # Track directory statistics
        dir_stats = {}

        # Analyze each file
        for root, dirs, files in os.walk(self.project_path):
            # Skip ignored directories
            dirs[:] = [d for d in dirs if not any(x in d for x in ['node_modules', 'venv', '.git', '__pycache__', 'build', 'dist'])]
            
            rel_root = os.path.relpath(root, self.project_path)
            if rel_root == '.':
                rel_root = ''
                
            # Initialize directory statistics
            dir_stats[rel_root] = {
                'total_files': 0,
                'code_files': 0,
                'languages': {},
                'frameworks': set(),
                'patterns': {
                    'classes': 0,
                    'functions': 0,
                    'imports': 0
                }
            }

            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, self.project_path)
                
                # Update directory statistics
                dir_stats[rel_root]['total_files'] += 1
                
                # Analyze code files
                file_ext = os.path.splitext(file)[1].lower()
                if file_ext in ['.py', '.js', '.ts', '.tsx', '.kt', '.php', '.swift', '.cpp', '.c', '.h', '.hpp', '.cs', '.csx']:
                    structure['files'].append(rel_path)
                    dir_stats[rel_root]['code_files'] += 1
                    
                    # Update language statistics
                    lang = self._get_language_from_ext(file_ext)
                    dir_stats[rel_root]['languages'][lang] = dir_stats[rel_root]['languages'].get(lang, 0) + 1
                    structure['languages'][lang] = structure['languages'].get(lang, 0) + 1
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            structure['code_contents'][rel_path] = content
                            
                            # Analyze based on file type
                            self._analyze_file_by_type(file_ext, content, rel_path, structure, dir_stats[rel_root])
                            
                    except Exception as e:
                        print(f"⚠️ Error reading file {rel_path}: {e}")
                        continue

                # Classify config files
                elif file.endswith(('.json', '.ini', '.conf')):
                    structure['config_files'].append(rel_path)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            structure['patterns']['configurations'].append({
                                'file': rel_path,
                                'content': content
                            })
                    except Exception as e:
                        print(f"⚠️ Error reading config file {rel_path}: {e}")
                        continue

            # Add directory structure information
            if rel_root:
                structure['directory_structure'][rel_root] = {
                    'stats': dir_stats[rel_root],
                    'parent': os.path.dirname(rel_root) or None
                }

        # Analyze directory patterns
        self._analyze_directory_patterns(structure, dir_stats)
        
        return structure

    def _get_language_from_ext(self, ext: str) -> str:
        """Get programming language from file extension."""
        lang_map = {
            '.py': 'Python',
            '.js': 'JavaScript',
            '.ts': 'TypeScript',
            '.tsx': 'TypeScript/React',
            '.kt': 'Kotlin',
            '.php': 'PHP',
            '.swift': 'Swift',
            '.cpp': 'C++',
            '.c': 'C',
            '.h': 'C/C++ Header',
            '.hpp': 'C++ Header',
            '.cs': 'C#',
            '.csx': 'C# Script',
        }
        return lang_map.get(ext, 'Unknown')

    def _analyze_file_by_type(self, file_ext: str, content: str, rel_path: str, structure: Dict[str, Any], dir_stats: Dict[str, Any]):
        """Analyze file based on its type and update both structure and directory statistics."""
        # Language specific analysis
        if file_ext == '.py':
            self._analyze_python_file(content, rel_path, structure)
        elif file_ext == '.js':
            self._analyze_js_file(content, rel_path, structure)
        elif file_ext in ['.ts', '.tsx']:
            self._analyze_ts_file(content, rel_path, structure)
        elif file_ext == '.php':
            self._analyze_php_file(content, rel_path, structure)
        elif file_ext in ['.cs', '.csx']:
            self._analyze_csharp_file(content, rel_path, structure)
        elif file_ext == '.rb':
            self._analyze_ruby_file(content, rel_path, structure)
        elif file_ext == '.go':
            self._analyze_go_file(content, rel_path, structure)
        elif file_ext in ['.cpp', '.hpp', '.cc', '.cxx', '.h++']:
            self._analyze_cpp_file(content, rel_path, structure)
        elif file_ext in ['.c', '.h']:
            self._analyze_c_file(content, rel_path, structure)
        elif file_ext == '.kt':
            self._analyze_kotlin_file(content, rel_path, structure)
        elif file_ext == '.swift':
            self._analyze_swift_file(content, rel_path, structure)
        # Update directory statistics
        dir_stats['patterns']['classes'] += len([p for p in structure['patterns']['class_patterns'] if p['file'] == rel_path])
        dir_stats['patterns']['functions'] += len([p for p in structure['patterns']['function_patterns'] if p['file'] == rel_path])
        dir_stats['patterns']['imports'] += len([imp for imp in structure['patterns']['imports'] if imp in rel_path])

    def _analyze_directory_patterns(self, structure: Dict[str, Any], dir_stats: Dict[str, Any]):
        """Analyze directory organization patterns."""
        for dir_path, stats in dir_stats.items():
            if not dir_path:  # Skip root directory
                continue
                
            # Analyze directory naming convention
            dir_name = os.path.basename(dir_path)
            if dir_name.islower():
                pattern = 'lowercase'
            elif dir_name.isupper():
                pattern = 'uppercase'
            elif '_' in dir_name:
                pattern = 'snake_case'
            elif '-' in dir_name:
                pattern = 'kebab-case'
            else:
                pattern = 'mixed'
                
            # Analyze directory purpose
            purpose = []
            if any(x in dir_name.lower() for x in ['test', 'spec', 'mock']):
                purpose.append('testing')
            if any(x in dir_name.lower() for x in ['util', 'helper', 'common', 'shared']):
                purpose.append('utilities')
            if any(x in dir_name.lower() for x in ['model', 'entity', 'domain']):
                purpose.append('domain')
            if any(x in dir_name.lower() for x in ['controller', 'handler', 'service']):
                purpose.append('business_logic')
            if any(x in dir_name.lower() for x in ['view', 'template', 'component']):
                purpose.append('presentation')
                
            # Add directory pattern
            structure['patterns']['directory_patterns'].append({
                'path': dir_path,
                'name_pattern': pattern,
                'purpose': purpose,
                'languages': stats['languages'],
                'total_files': stats['total_files'],
                'code_files': stats['code_files'],
                'code_metrics': stats['patterns']
            })

    def _generate_ai_rules(self, project_info: Dict[str, Any]) -> Dict[str, Any]:
        """Generate rules using OpenAI based on project analysis."""
        try:
            # Analyze project
            project_structure = self._analyze_project_structure()
            
            # Create detailed prompt
            prompt = f"""As an AI assistant working in Cursor IDE, analyze this project to understand how you should behave and generate code that perfectly matches the project's patterns and standards.

Project Overview:
Language: {project_info.get('language', 'unknown')}
Framework: {project_info.get('framework', 'none')}
Type: {project_info.get('type', 'generic')}
Description: {project_info.get('description', 'Generic Project')}
Primary Purpose: Code generation and project analysis

Project Metrics:
- Files & Structure:
  - Total Files: {len(project_structure['files'])}
  - Config Files: {len(project_structure['config_files'])}
- Dependencies:
  - Frameworks: {', '.join(project_structure['frameworks']) or 'none'}
  - Core Dependencies: {', '.join(list(project_structure['dependencies'].keys())[:10])}
  - Total Dependencies: {len(project_structure['dependencies'])}

Project Ecosystem:
1. Development Environment:
- Project Structure:
{chr(10).join([f"- {f}" for f in project_structure['files'] if f.endswith(('.json', '.md', '.env', '.gitignore'))][:5])}
- IDE Configuration:
{chr(10).join([f"- {f}" for f in project_structure['files'] if '.vscode' in f or '.idea' in f][:5])}
- Build System:
{chr(10).join([f"- {f}" for f in project_structure['files'] if f in ['setup.py', 'requirements.txt', 'package.json', 'Makefile', 'composer.json', 'Gemfile', 'go.mod', 'CMakeLists.txt', 'build.gradle', 'pom.xml', 'webpack.config.js']])}

2. Project Components:
- Core Modules:
{chr(10).join([f"- {f}: {sum(1 for p in project_structure['patterns']['function_patterns'] if p['file'] == f)} functions" for f in project_structure['files'] if f.endswith('.py, .js, .ts, .tsx, .kt, .php, .swift, .cpp, .c, .h, .hpp, .cs, .csx') and not any(x in f.lower() for x in ['setup', 'config'])][:5])}
- Support Modules:
{chr(10).join([f"- {f}" for f in project_structure['files'] if any(x in f.lower() for x in ['util', 'helper', 'common', 'shared'])][:5])}
- Templates:
{chr(10).join([f"- {f}" for f in project_structure['files'] if 'template' in f.lower()][:5])}

3. Module Organization Analysis:
- Core Module Functions:
{chr(10).join([f"- {f}: Primary module handling {f.split('_')[0].title()} functionality" for f in project_structure['files'] if f.endswith('.py, .js, .ts, .tsx, .kt, .php, .swift, .cpp, .c, .h, .hpp, .cs, .csx') and not any(x in f.lower() for x in ['setup', 'config'])][:5])}

- Module Dependencies:
{chr(10).join([f"- {f} depends on: {', '.join(list(set([imp.split('.')[0] for imp in project_structure['patterns']['imports'] if imp in f])))}" for f in project_structure['files'] if f.endswith('.py, .js, .ts, .tsx, .kt, .php, .swift, .cpp, .c, .h, .hpp, .cs, .csx')][:5])}

- Module Responsibilities:
Please analyze each module's code and describe its core responsibilities based on:
1. Function and class names
2. Import statements
3. Code patterns and structures
4. Documentation strings
5. Variable names and usage
6. Error handling patterns
7. Performance optimization techniques

- Module Organization Rules:
Based on the codebase analysis, identify and describe:
1. Module organization patterns
2. Dependency management approaches
3. Code structure conventions
4. Naming conventions
5. Documentation practices
6. Error handling strategies
7. Performance optimization patterns

Code Sample Analysis:
{chr(10).join(f"File: {file}:{chr(10)}{content[:10000]}..." for file, content in list(project_structure['code_contents'].items())[:50])}

Based on this detailed analysis, create behavior rules for AI to:
1. Replicate the project's exact code style and patterns
2. Match naming conventions precisely
3. Follow identical error handling patterns
4. Copy performance optimization techniques
5. Maintain documentation consistency
6. Keep current code organization
7. Preserve module boundaries
8. Use established logging methods
9. Follow configuration patterns

Return a JSON object defining AI behavior rules:
{{"ai_behavior": {{
    "code_generation": {{
        "style": {{
            "prefer": [],
            "avoid": []
        }},
        "error_handling": {{
            "prefer": [],
            "avoid": []
        }},
        "performance": {{
            "prefer": [],
            "avoid": []
        }},
        "suggest_patterns": {{
            "improve": [],
            "avoid": []
        }},
        "module_organization": {{
            "structure": [],  # Analyze and describe the current module structure
            "dependencies": [],  # Analyze actual dependencies between modules
            "responsibilities": {{}},  # Analyze and describe each module's core responsibilities
            "rules": [],  # Extract rules from actual code organization patterns
            "naming": {{}}  # Extract naming conventions from actual code
        }}
    }}
}}}}

Critical Guidelines for AI:
1. NEVER deviate from existing code patterns
2. ALWAYS match the project's exact style
3. MAINTAIN the current complexity level
4. COPY the existing skill level approach
5. PRESERVE all established practices
6. REPLICATE the project's exact style
7. UNDERSTAND pattern purposes"""
    
            # Get AI response
            response = self.client.chat.completions.create(
                model="google/gemini-flash-1.5",
                messages=[
                    {"role": "system", "content": "You are a helpful AI code analysis assistant."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=8192,
                temperature=0.7
            )
            
            # Извлечение ответа
            response_text = response.choices[0].message.content
            
            # Извлечение JSON
            json_match = re.search(r'({[\s\S]*})', response_text)
            if not json_match:
                print("⚠️ No JSON found in AI response")
                raise ValueError("Invalid AI response format")
                
            json_str = json_match.group(1)
            
            try:
                ai_rules = json.loads(json_str)
                
                if not isinstance(ai_rules, dict) or 'ai_behavior' not in ai_rules:
                    print("⚠️ Invalid JSON structure in AI response")
                    raise ValueError("Invalid AI rules structure")
                    
                return ai_rules
                
            except json.JSONDecodeError as e:
                print(f"⚠️ Error parsing AI response JSON: {e}")
                raise
                
        except Exception as e:
            print(f"⚠️ Error generating AI rules: {e}")
            raise

    def _generate_project_description(self, project_structure: Dict[str, Any]) -> str:
        """Generate project description using AI based on project analysis."""
        try:
            # Analyze core modules
            core_modules = []
            for file in project_structure.get('files', []):
                if file.endswith('.py') and not any(x in file.lower() for x in ['setup', 'config', 'test']):
                    module_info = {
                        'name': file,
                        'classes': [c for c in project_structure['patterns']['class_patterns'] if c['file'] == file],
                        'functions': [f for f in project_structure['patterns']['function_patterns'] if f['file'] == file],
                        'imports': [imp for imp in project_structure['patterns']['imports'] if imp in file]
                    }
                    core_modules.append(module_info)

            # Analyze main patterns
            main_patterns = {
                'error_handling': project_structure.get('patterns', {}).get('error_patterns', []),
                'performance': project_structure.get('patterns', {}).get('performance_patterns', []),
                'code_organization': project_structure.get('patterns', {}).get('code_organization', [])
            }

            # Create detailed prompt for AI
            prompt = f"""Analyze this project structure and create a detailed description (2-3 sentences) that captures its essence:

Project Overview:
1. Core Modules Analysis:
{chr(10).join([f"- {m['name']}: {len(m['classes'])} classes, {len(m['functions'])} functions" for m in core_modules])}

2. Module Responsibilities:
{chr(10).join([f"- {m['name']}: Main purpose indicated by {', '.join([c['name'] for c in m['classes'][:2]])}" for m in core_modules if m['classes']])}

3. Technical Implementation:
- Error Handling: {len(main_patterns['error_handling'])} patterns found
- Performance Optimizations: {len(main_patterns['performance'])} patterns found
- Code Organization: {len(main_patterns['code_organization'])} patterns found

4. Project Architecture:
- Total Files: {len(project_structure.get('files', []))}
- Core Python Modules: {len(core_modules)}
- External Dependencies: {len(project_structure.get('dependencies', {}))}

Based on this analysis, create a description that covers:
1. The project's main purpose and functionality
2. Key technical features and implementation approach
3. Target users and primary use cases
4. Unique characteristics or innovations

Format: Return a clear, concise description focusing on what makes this project unique.
Do not include technical metrics in the description."""

            # Get AI response
            response = self.client.chat.completions.create(
                model="google/gemini-flash-1.5",
                messages=[
                    {"role": "system", "content": "You are a helpful AI project description generator."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=8192,
                temperature=0.7
            )
            
            description = response.choices[0].message.content.strip()
            
            # Validate description length and content
            if len(description.split()) > 100:  # Length limit
                description = ' '.join(description.split()[:100]) + '...'
            
            return description
            
        except Exception as e:
            print(f"⚠️ Error generating project description: {e}")
            return "A software project with automated analysis and rule generation capabilities."

    def _generate_markdown_rules(self, project_info: Dict[str, Any], ai_rules: Dict[str, Any]) -> str:
        """Generate rules in markdown format."""
        timestamp = self._get_timestamp()
        description = project_info.get('description', 'A software project with automated analysis and rule generation capabilities.')
        
        markdown = f"""# Project Rules

## Project Information
- **Version**: {project_info.get('version', '1.0')}
- **Last Updated**: {timestamp}
- **Name**: {project_info.get('name', 'Unknown')}
- **Language**: {project_info.get('language', 'unknown')}
- **Framework**: {project_info.get('framework', 'none')}
- **Type**: {project_info.get('type', 'application')}

## Project Description
{description}

## AI Behavior Rules

### Code Generation Style
#### Preferred Patterns
"""
        # Add preferred code generation patterns
        for pattern in ai_rules['ai_behavior']['code_generation']['style']['prefer']:
            markdown += f"- {pattern}\n"
            
        markdown += "\n#### Patterns to Avoid\n"
        for pattern in ai_rules['ai_behavior']['code_generation']['style']['avoid']:
            markdown += f"- {pattern}\n"
            
        markdown += "\n### Error Handling\n#### Preferred Patterns\n"
        for pattern in ai_rules['ai_behavior']['code_generation']['error_handling']['prefer']:
            markdown += f"- {pattern}\n"
            
        markdown += "\n#### Patterns to Avoid\n"
        for pattern in ai_rules['ai_behavior']['code_generation']['error_handling']['avoid']:
            markdown += f"- {pattern}\n"
            
        markdown += "\n### Performance\n#### Preferred Patterns\n"
        for pattern in ai_rules['ai_behavior']['code_generation']['performance']['prefer']:
            markdown += f"- {pattern}\n"
            
        markdown += "\n#### Patterns to Avoid\n"
        for pattern in ai_rules['ai_behavior']['code_generation']['performance']['avoid']:
            markdown += f"- {pattern}\n"
            
        markdown += "\n### Module Organization\n#### Structure\n"
        for item in ai_rules['ai_behavior']['code_generation']['module_organization']['structure']:
            markdown += f"- {item}\n"
            
        markdown += "\n#### Dependencies\n"
        for dep in ai_rules['ai_behavior']['code_generation']['module_organization']['dependencies']:
            markdown += f"- {dep}\n"
            
        markdown += "\n#### Module Responsibilities\n"
        for module, resp in ai_rules['ai_behavior']['code_generation']['module_organization']['responsibilities'].items():
            markdown += f"- **{module}**: {resp}\n"
            
        markdown += "\n#### Rules\n"
        for rule in ai_rules['ai_behavior']['code_generation']['module_organization']['rules']:
            markdown += f"- {rule}\n"
            
        markdown += "\n#### Naming Conventions\n"
        for category, convention in ai_rules['ai_behavior']['code_generation']['module_organization']['naming'].items():
            markdown += f"- **{category}**: {convention}\n"
            
        return markdown

    def generate_rules_file(self, project_info: Dict[str, Any] = None, format: str = 'json') -> str:
        """Generate the .cursorrules file based on project analysis and AI suggestions."""
        try:
            # Use analyzer if no project_info provided
            if project_info is None:
                project_info = self.analyzer.analyze_project_for_rules()
            
            # Analyze project structure
            project_structure = self._analyze_project_structure()
            
            # Generate AI rules
            ai_rules = self._generate_ai_rules(project_info)
            
            # Generate project description
            description = self._generate_project_description(project_structure)
            project_info['description'] = description
            
            # Create rules file path
            rules_file = os.path.join(self.project_path, '.cursorrules')
            
            if format.lower() == 'markdown':
                content = self._generate_markdown_rules(project_info, ai_rules)
                with open(rules_file, 'w', encoding='utf-8') as f:
                    f.write(content)
            else:  # JSON format
                rules = {
                    "version": "1.0",
                    "last_updated": self._get_timestamp(),
                    "project": {
                        **project_info,
                        "description": description
                    },
                    "ai_behavior": ai_rules['ai_behavior']
                }
                with open(rules_file, 'w', encoding='utf-8') as f:
                    json.dump(rules, f, indent=2)
            
            return rules_file
                
        except Exception as e:
            print(f"❌ Failed to generate rules: {e}")
            raise 

    def _analyze_python_file(self, content: str, rel_path: str, structure: Dict[str, Any]):
        """Analyze Python file content."""
        # Find imports and dependencies
        imports = re.findall(self.PATTERNS['import']['python'], content, re.MULTILINE)
        structure['dependencies'].update({imp: True for imp in imports})
        structure['patterns']['imports'].extend(imports)
        
        # Find classes and their patterns
        class_patterns = re.finditer(self.PATTERNS['class']['python'], content)
        for match in class_patterns:
            class_name = match.group(1)
            inheritance = match.group(2) if match.group(2) else ''
            structure['patterns']['class_patterns'].append({
                'name': class_name,
                'inheritance': inheritance,
                'file': rel_path
            })
        
        # Find and analyze functions
        function_patterns = re.finditer(self.PATTERNS['function']['python'], content)
        for match in function_patterns:
            func_name = match.group(1)
            params = match.group(2)
            return_type = match.group(3) if match.group(3) else None
            structure['patterns']['function_patterns'].append({
                'name': func_name,
                'parameters': params,
                'return_type': return_type,
                'file': rel_path
            })

    def _analyze_js_file(self, content: str, rel_path: str, structure: Dict[str, Any]):
        """Analyze JavaScript file content."""
        # Find imports
        imports = re.findall(self.PATTERNS['import']['javascript'], content)
        imports = [imp[0] or imp[1] for imp in imports]  # Flatten tuples from regex groups
        structure['dependencies'].update({imp: True for imp in imports})
        structure['patterns']['imports'].extend(imports)
        
        # Find classes
        classes = re.finditer(self.PATTERNS['class']['javascript'], content)
        for match in classes:
            structure['patterns']['class_patterns'].append({
                'name': match.group(1),
                'inheritance': match.group(2) if match.group(2) else '',
                'file': rel_path
            })
        
        # Find functions (including arrow functions)
        functions = re.finditer(self.PATTERNS['function']['javascript'], content)
        for match in functions:
            name = match.group(1) or match.group(2)  # Get name from either function or variable
            structure['patterns']['function_patterns'].append({
                'name': name,
                'parameters': match.group(3),
                'file': rel_path
            })
            
        # Find object methods
        methods = re.finditer(self.PATTERNS['method'], content)
        for match in methods:
            structure['patterns']['function_patterns'].append({
                'name': match.group(1),
                'parameters': match.group(2),
                'type': 'method',
                'file': rel_path
            })
            
        # Find variables and constants
        variables = re.finditer(self.PATTERNS['variable'], content)
        for match in variables:
            structure['patterns']['variable_patterns'].append({
                'name': match.group(1),
                'value': match.group(2).strip(),
                'file': rel_path
            })
            
        # Find error handling patterns
        try_blocks = re.finditer(self.PATTERNS['error'], content)
        for match in try_blocks:
            structure['patterns']['error_patterns'].append({
                'exception_var': match.group(1),
                'file': rel_path
            })
            
        # Find async/await patterns
        if 'async' in content:
            structure['patterns']['performance_patterns'].append({
                'file': rel_path,
                'has_async': True
            })

    def _analyze_kotlin_file(self, content: str, rel_path: str, structure: Dict[str, Any]):
        """Analyze Kotlin file content."""
        # Find imports
        imports = re.findall(self.PATTERNS['import']['kotlin'], content)
        structure['dependencies'].update({imp: True for imp in imports})
        structure['patterns']['imports'].extend(imports)
        
        # Find classes
        classes = re.finditer(self.PATTERNS['class']['kotlin'], content)
        for match in classes:
            structure['patterns']['class_patterns'].append({
                'name': match.group(1),
                'inheritance': match.group(2).strip() if match.group(2) else '',
                'file': rel_path
            })
        
        # Find functions
        functions = re.finditer(self.PATTERNS['function']['kotlin'], content)
        for match in functions:
            structure['patterns']['function_patterns'].append({
                'name': match.group(1),
                'parameters': match.group(2),
                'return_type': match.group(3).strip() if match.group(3) else None,
                'file': rel_path
            })

    def _analyze_php_file(self, content: str, rel_path: str, structure: Dict[str, Any]):
        """Analyze PHP file content."""
        try:
            # Find imports/requires/namespaces
            imports = []
            lines = content.split('\n')
            
            # Process each line for imports/namespaces
            for line in lines:
                matches = re.finditer(r'(?:namespace\s+([a-zA-Z0-9_\\]+))|(?:use\s+(?:\\)?([a-zA-Z0-9_\\]+)(?:\s+as\s+[a-zA-Z0-9_]+)?)', line)
                for match in matches:
                    import_value = next((g for g in match.groups() if g is not None), None)
                    if import_value and import_value.strip():
                        imports.append(import_value.strip())
            
            if imports:
                structure['dependencies'].update({imp: True for imp in imports})
                structure['patterns']['imports'].extend(imports)
            
            # Find classes
            classes = []
            class_pattern = r'(?:abstract\s+)?class\s+(\w+)(?:\s+extends\s+(?:\\)?[a-zA-Z0-9_\\]+)?(?:\s+implements\s+(?:\\)?[a-zA-Z0-9_\\]+(?:\s*,\s*(?:\\)?[a-zA-Z0-9_\\]+)*)?',
            
            for i, line in enumerate(lines, 1):
                matches = re.finditer(class_pattern, line)
                for match in matches:
                    class_info = {
                        'name': match.group(1),
                        'file': rel_path,
                        'line': i
                    }
                    classes.append(class_info)
            
            structure['patterns']['class_patterns'].extend(classes)
            
            # Find functions
            functions = []
            function_pattern = r'(?:public\s+|private\s+|protected\s+)?(?:static\s+)?function\s+(\w+)\s*\([^)]*\)'
            
            for i, line in enumerate(lines, 1):
                matches = re.finditer(function_pattern, line)
                for match in matches:
                    func_info = {
                        'name': match.group(1),
                        'file': rel_path,
                        'line': i
                    }
                    functions.append(func_info)
            
            structure['patterns']['function_patterns'].extend(functions)
                    
        except Exception as e:
            pass

    def _analyze_swift_file(self, content: str, rel_path: str, structure: Dict[str, Any]):
        """Analyze Swift file content."""
        # Find imports
        imports = re.findall(self.PATTERNS['import']['swift'], content)
        structure['dependencies'].update({imp: True for imp in imports})
        structure['patterns']['imports'].extend(imports)
        
        # Find classes and protocols
        classes = re.finditer(self.PATTERNS['class']['swift'], content)
        for match in classes:
            structure['patterns']['class_patterns'].append({
                'name': match.group(1),
                'inheritance': match.group(2).strip() if match.group(2) else '',
                'file': rel_path
            })
        
        # Find functions
        functions = re.finditer(self.PATTERNS['function']['swift'], content)
        for match in functions:
            structure['patterns']['function_patterns'].append({
                'name': match.group(1),
                'parameters': match.group(2),
                'return_type': match.group(3).strip() if match.group(3) else None,
                'file': rel_path
            })

    def _analyze_ts_file(self, content: str, rel_path: str, structure: Dict[str, Any]):
        """Analyze TypeScript/TSX file content."""
        # Find imports
        imports = re.findall(self.PATTERNS['import']['typescript'], content)
        structure['dependencies'].update({imp: True for imp in imports})
        structure['patterns']['imports'].extend(imports)
        
        # Find interfaces and types
        interfaces = re.finditer(self.PATTERNS['interface'], content)
        for match in interfaces:
            structure['patterns']['class_patterns'].append({
                'name': match.group(1),
                'type': 'interface/type',
                'inheritance': match.group(2).strip() if match.group(2) else '',
                'file': rel_path
            })
        
        # Find classes and components
        classes = re.finditer(self.PATTERNS['class']['typescript'], content)
        for match in classes:
            structure['patterns']['class_patterns'].append({
                'name': match.group(1),
                'type': 'class/component',
                'inheritance': match.group(2).strip() if match.group(2) else '',
                'file': rel_path
            })
        
        # Find functions and hooks
        functions = re.finditer(self.PATTERNS['function']['typescript'], content)
        for match in functions:
            name = match.group(1)
            is_hook = name.startswith('use') and name[3].isupper()
            structure['patterns']['function_patterns'].append({
                'name': name,
                'type': 'hook' if is_hook else 'function',
                'parameters': match.group(2),
                'return_type': match.group(3).strip() if match.group(3) else None,
                'file': rel_path
            })
        
        # Find JSX components in TSX files
        if rel_path.endswith('.tsx'):
            components = re.finditer(self.PATTERNS['jsx_component'], content)
            for match in components:
                component_name = match.group(1)
                if component_name[0].isupper():  # Custom components start with uppercase
                    structure['patterns']['class_patterns'].append({
                        'name': component_name,
                        'type': 'jsx_component',
                        'file': rel_path
                    }) 

    def _analyze_cpp_file(self, content: str, rel_path: str, structure: Dict[str, Any]):
        """Analyze C++ file content."""
        # Find includes
        includes = re.findall(self.PATTERNS['import']['cpp'], content)
        structure['dependencies'].update({inc: True for inc in includes})
        structure['patterns']['imports'].extend(includes)
        
        # Find classes and structs
        classes = re.finditer(self.PATTERNS['class']['cpp'], content)
        for match in classes:
            structure['patterns']['class_patterns'].append({
                'name': match.group(1),
                'inheritance': match.group(2) if match.group(2) else '',
                'file': rel_path
            })
        
        # Find functions and methods
        functions = re.finditer(self.PATTERNS['function']['cpp'], content)
        for match in functions:
            structure['patterns']['function_patterns'].append({
                'name': match.group(1),
                'parameters': match.group(2),
                'file': rel_path
            })
            
        # Find templates
        templates = re.finditer(r'template\s*<([^>]+)>', content)
        for match in templates:
            structure['patterns']['code_organization'].append({
                'type': 'template',
                'parameters': match.group(1),
                'file': rel_path
            })
            
        # Find namespaces
        namespaces = re.finditer(r'namespace\s+(\w+)\s*{', content)
        for match in namespaces:
            structure['patterns']['code_organization'].append({
                'type': 'namespace',
                'name': match.group(1),
                'file': rel_path
            })

    def _analyze_c_file(self, content: str, rel_path: str, structure: Dict[str, Any]):
        """Analyze C file content."""
        # Find includes
        includes = re.findall(self.PATTERNS['import']['c'], content)
        structure['dependencies'].update({inc: True for inc in includes})
        structure['patterns']['imports'].extend(includes)
        
        # Find structs and unions
        structs = re.finditer(self.PATTERNS['class']['c'], content)
        for match in structs:
            structure['patterns']['class_patterns'].append({
                'name': match.group(1),
                'type': 'struct/union',
                'file': rel_path
            })
        
        # Find functions
        functions = re.finditer(self.PATTERNS['function']['c'], content)
        for match in functions:
            structure['patterns']['function_patterns'].append({
                'name': match.group(1),
                'parameters': match.group(2),
                'file': rel_path
            })
            
        # Find macros
        macros = re.finditer(r'#define\s+(\w+)(?:\(([^)]*)\))?\s+(.+)', content)
        for match in macros:
            structure['patterns']['code_organization'].append({
                'type': 'macro',
                'name': match.group(1),
                'parameters': match.group(2) if match.group(2) else '',
                'value': match.group(3),
                'file': rel_path
            })
            
        # Find typedefs
        typedefs = re.finditer(r'typedef\s+(?:struct|enum|union)?\s*(\w+)\s+(\w+);', content)
        for match in typedefs:
            structure['patterns']['code_organization'].append({
                'type': 'typedef',
                'original_type': match.group(1),
                'new_type': match.group(2),
                'file': rel_path
            }) 
            
        # Find annotations
        annotations = re.finditer(r'@(\w+)(?:\((.*?)\))?', content)
        for match in annotations:
            structure['patterns']['code_organization'].append({
                'type': 'annotation',
                'name': match.group(1),
                'parameters': match.group(2) if match.group(2) else '',
                'file': rel_path
            })

    def _analyze_csharp_file(self, content: str, rel_path: str, structure: Dict[str, Any]):
        """Analyze C# file content."""
        # Find using statements
        imports = re.findall(self.PATTERNS['import']['csharp'], content)
        structure['dependencies'].update({imp: True for imp in imports})
        structure['patterns']['imports'].extend(imports)
        
        # Find classes and interfaces
        classes = re.finditer(self.PATTERNS['class']['csharp'], content)
        for match in classes:
            inheritance = match.group(2)
            if inheritance:
                inheritance_parts = [p.strip() for p in inheritance.split(',')]
                base_class = inheritance_parts[0] if inheritance_parts else ''
                interfaces = inheritance_parts[1:] if len(inheritance_parts) > 1 else []
            else:
                base_class = ''
                interfaces = []
                
            structure['patterns']['class_patterns'].append({
                'name': match.group(1),
                'inheritance': base_class,
                'interfaces': interfaces,
                'file': rel_path
            })
        
        # Find methods
        methods = re.finditer(self.PATTERNS['function']['csharp'], content)
        for match in methods:
            structure['patterns']['function_patterns'].append({
                'return_type': match.group(1),
                'name': match.group(2),
                'parameters': match.group(3),
                'file': rel_path
            })
            
        # Find properties
        properties = re.finditer(r'(?:public|private|protected|internal)?\s*(\w+)\s+(\w+)\s*{\s*get;\s*(?:private\s*)?set;\s*}', content)
        for match in properties:
            structure['patterns']['code_organization'].append({
                'type': 'property',
                'type_name': match.group(1),
                'name': match.group(2),
                'file': rel_path
            })

    