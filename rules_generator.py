import os
import json
from typing import Dict, Any, List
from datetime import datetime
import google.generativeai as genai
import re
from rules_analyzer import RulesAnalyzer
from dotenv import load_dotenv

class RulesGenerator:
    def __init__(self, project_path: str):
        self.project_path = project_path
        self.analyzer = RulesAnalyzer(project_path)
        
        # Load environment variables from .env
        load_dotenv()
        
        # Initialize Gemini AI
        try:
            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                raise ValueError("GEMINI_API_KEY is required")

            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel(
                model_name="gemini-2.0-flash-exp",
                generation_config={
                    "temperature": 0.7,
                    "top_p": 0.95,
                    "top_k": 40,
                    "max_output_tokens": 8192,
                }
            )
            self.chat_session = self.model.start_chat(history=[])
            
        except Exception as e:
            print(f"\n⚠️ Error when initializing Gemini AI: {e}")
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
            'patterns': {
                'classes': [],
                'functions': [],
                'imports': [],
                'error_handling': [],
                'configurations': [],
                'naming_patterns': {},  # Track naming conventions
                'code_organization': [], # Track code organization patterns
                'variable_patterns': [], # Track variable naming and usage
                'function_patterns': [], # Track function patterns
                'class_patterns': [],    # Track class patterns
                'error_patterns': [],    # Track error handling patterns
                'performance_patterns': [] # Track performance patterns
            }
        }

        # Analyze each file
        for root, _, files in os.walk(self.project_path):
            if any(x in root for x in ['node_modules', 'venv', '.git', '__pycache__', 'build', 'dist']):
                continue

            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, self.project_path)
                
                # Analyze code files
                if file.endswith(('.py', '.js', '.ts', '.tsx', '.kt', '.php', '.swift')):
                    structure['files'].append(rel_path)
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            structure['code_contents'][rel_path] = content
                            
                            # Common code analysis patterns
                            file_ext = os.path.splitext(file)[1]
                            
                            # Language specific patterns
                            if file_ext == '.py':
                                self._analyze_python_file(content, rel_path, structure)
                            elif file_ext == '.js':
                                self._analyze_js_file(content, rel_path, structure)
                            elif file_ext in ['.ts', '.tsx']:
                                self._analyze_ts_file(content, rel_path, structure)
                            elif file_ext == '.kt':
                                self._analyze_kotlin_file(content, rel_path, structure)
                            elif file_ext == '.php':
                                self._analyze_php_file(content, rel_path, structure)
                            elif file_ext == '.swift':
                                self._analyze_swift_file(content, rel_path, structure)
                                    
                    except Exception as e:
                        print(f"⚠️ Error reading file {rel_path}: {e}")
                        continue

                # Classify files
                if file.endswith(('.json', '.yaml', '.ini', '.conf')):
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

        return structure

    def _generate_ai_rules(self, project_info: Dict[str, Any]) -> Dict[str, Any]:
        """Generate rules using Gemini AI based on project analysis."""
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
{chr(10).join([f"- {f}" for f in project_structure['files'] if f in ['setup.py', 'requirements.txt', 'package.json', 'Makefile']])}

2. Project Components:
- Core Modules:
{chr(10).join([f"- {f}: {sum(1 for p in project_structure['patterns']['function_patterns'] if p['file'] == f)} functions" for f in project_structure['files'] if f.endswith('.py') and not any(x in f.lower() for x in ['setup', 'config'])][:5])}
- Support Modules:
{chr(10).join([f"- {f}" for f in project_structure['files'] if any(x in f.lower() for x in ['util', 'helper', 'common', 'shared'])][:5])}
- Templates:
{chr(10).join([f"- {f}" for f in project_structure['files'] if 'template' in f.lower()][:5])}

3. Module Organization Analysis:
- Core Module Functions:
{chr(10).join([f"- {f}: Primary module handling {f.split('_')[0].title()} functionality" for f in project_structure['files'] if f.endswith('.py') and not any(x in f.lower() for x in ['setup', 'config'])][:5])}

- Module Dependencies:
{chr(10).join([f"- {f} depends on: {', '.join(list(set([imp.split('.')[0] for imp in project_structure['patterns']['imports'] if imp in f])))}" for f in project_structure['files'] if f.endswith('.py')][:5])}

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
7. UNDERSTAND pattern purposes
8. FOLLOW existing workflows
9. RESPECT current architecture
10. MIRROR documentation style"""

            # Get AI response
            response = self.chat_session.send_message(prompt)
            
            # Extract JSON
            json_match = re.search(r'({[\s\S]*})', response.text)
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

    def generate_rules_file(self, project_info: Dict[str, Any] = None) -> str:
        """Generate the .cursorrules file based on project analysis and AI suggestions."""
        try:
            # Use analyzer if no project_info provided
            if project_info is None:
                project_info = self.analyzer.analyze_project_for_rules()
            
            # Generate AI rules
            ai_rules = self._generate_ai_rules(project_info)
            
            # Create rules with AI suggestions
            rules = {
                "version": "1.0",
                "last_updated": self._get_timestamp(),
                "project": project_info,
                "ai_behavior": ai_rules['ai_behavior']
            }
            
            # Write to file
            rules_file = os.path.join(self.project_path, '.cursorrules')
            with open(rules_file, 'w', encoding='utf-8') as f:
                json.dump(rules, f, indent=2)
            
            print("✅ Successfully generated rules using Gemini AI")
            return rules_file
                
        except Exception as e:
            print(f"❌ Failed to generate rules: {e}")
            raise 

    def _analyze_python_file(self, content: str, rel_path: str, structure: Dict[str, Any]):
        """Analyze Python file content."""
        # Find imports and dependencies
        imports = re.findall(r'^(?:from|import)\s+([a-zA-Z0-9_\.]+)', content, re.MULTILINE)
        structure['dependencies'].update({imp: True for imp in imports})
        structure['patterns']['imports'].extend(imports)
        
        # Find classes and their patterns
        classes = re.findall(r'class\s+(\w+)(?:\(.*?\))?:', content)
        structure['patterns']['classes'].extend(classes)
        
        # Analyze class patterns
        class_patterns = re.finditer(r'class\s+(\w+)(?:\((.*?)\))?\s*:', content)
        for match in class_patterns:
            class_name = match.group(1)
            inheritance = match.group(2) if match.group(2) else ''
            structure['patterns']['class_patterns'].append({
                'name': class_name,
                'inheritance': inheritance,
                'file': rel_path
            })
        
        # Find and analyze functions
        function_patterns = re.finditer(r'def\s+(\w+)\s*\((.*?)\)(?:\s*->\s*([^:]+))?\s*:', content)
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
        imports = re.findall(r'(?:import\s+.*?from\s+[\'"]([^\'\"]+)[\'"]|require\s*\([\'"]([^\'\"]+)[\'"]\))', content)
        imports = [imp[0] or imp[1] for imp in imports]  # Flatten tuples from regex groups
        structure['dependencies'].update({imp: True for imp in imports})
        structure['patterns']['imports'].extend(imports)
        
        # Find classes
        classes = re.finditer(r'class\s+(\w+)(?:\s+extends\s+(\w+))?\s*{', content)
        for match in classes:
            structure['patterns']['class_patterns'].append({
                'name': match.group(1),
                'inheritance': match.group(2) if match.group(2) else '',
                'file': rel_path
            })
        
        # Find functions (including arrow functions)
        functions = re.finditer(r'(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=\s*(?:function|\([^)]*\)\s*=>))\s*\((.*?)\)', content)
        for match in functions:
            name = match.group(1) or match.group(2)  # Get name from either function or variable
            structure['patterns']['function_patterns'].append({
                'name': name,
                'parameters': match.group(3),
                'file': rel_path
            })
            
        # Find object methods
        methods = re.finditer(r'(?:async\s+)?(\w+)\s*\((.*?)\)\s*{', content)
        for match in methods:
            structure['patterns']['function_patterns'].append({
                'name': match.group(1),
                'parameters': match.group(2),
                'type': 'method',
                'file': rel_path
            })
            
        # Find variables and constants
        variables = re.finditer(r'(?:const|let|var)\s+(\w+)\s*=\s*([^;]+)', content)
        for match in variables:
            structure['patterns']['variable_patterns'].append({
                'name': match.group(1),
                'value': match.group(2).strip(),
                'file': rel_path
            })
            
        # Find error handling patterns
        try_blocks = re.finditer(r'try\s*{[^}]*}\s*catch\s*\((\w+)\)', content)
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
        imports = re.findall(r'import\s+([^\n]+)', content)
        structure['dependencies'].update({imp: True for imp in imports})
        structure['patterns']['imports'].extend(imports)
        
        # Find classes
        classes = re.finditer(r'(?:class|interface|object)\s+(\w+)(?:\s*:\s*([^{]+))?', content)
        for match in classes:
            structure['patterns']['class_patterns'].append({
                'name': match.group(1),
                'inheritance': match.group(2).strip() if match.group(2) else '',
                'file': rel_path
            })
        
        # Find functions
        functions = re.finditer(r'fun\s+(\w+)\s*\((.*?)\)(?:\s*:\s*([^{]+))?', content)
        for match in functions:
            structure['patterns']['function_patterns'].append({
                'name': match.group(1),
                'parameters': match.group(2),
                'return_type': match.group(3).strip() if match.group(3) else None,
                'file': rel_path
            })

    def _analyze_php_file(self, content: str, rel_path: str, structure: Dict[str, Any]):
        """Analyze PHP file content."""
        # Find imports/requires
        imports = re.findall(r'(?:require|include)(?:_once)?\s*[\'"]([^\'"]+)[\'"]', content)
        structure['dependencies'].update({imp: True for imp in imports})
        structure['patterns']['imports'].extend(imports)
        
        # Find classes
        classes = re.finditer(r'class\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+([^{]+))?', content)
        for match in classes:
            structure['patterns']['class_patterns'].append({
                'name': match.group(1),
                'inheritance': match.group(2) if match.group(2) else '',
                'interfaces': match.group(3).strip() if match.group(3) else '',
                'file': rel_path
            })
        
        # Find functions
        functions = re.finditer(r'function\s+(\w+)\s*\((.*?)\)(?:\s*:\s*([^{]+))?', content)
        for match in functions:
            structure['patterns']['function_patterns'].append({
                'name': match.group(1),
                'parameters': match.group(2),
                'return_type': match.group(3).strip() if match.group(3) else None,
                'file': rel_path
            })

    def _analyze_swift_file(self, content: str, rel_path: str, structure: Dict[str, Any]):
        """Analyze Swift file content."""
        # Find imports
        imports = re.findall(r'import\s+([^\n]+)', content)
        structure['dependencies'].update({imp: True for imp in imports})
        structure['patterns']['imports'].extend(imports)
        
        # Find classes and protocols
        classes = re.finditer(r'(?:class|struct|protocol|enum)\s+(\w+)(?:\s*:\s*([^{]+))?', content)
        for match in classes:
            structure['patterns']['class_patterns'].append({
                'name': match.group(1),
                'inheritance': match.group(2).strip() if match.group(2) else '',
                'file': rel_path
            })
        
        # Find functions
        functions = re.finditer(r'func\s+(\w+)\s*\((.*?)\)(?:\s*->\s*([^{]+))?', content)
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
        imports = re.findall(r'(?:import|require)\s+.*?[\'"]([^\'\"]+)[\'"]', content)
        structure['dependencies'].update({imp: True for imp in imports})
        structure['patterns']['imports'].extend(imports)
        
        # Find interfaces and types
        interfaces = re.finditer(r'(?:interface|type)\s+(\w+)(?:\s+extends\s+([^{]+))?', content)
        for match in interfaces:
            structure['patterns']['class_patterns'].append({
                'name': match.group(1),
                'type': 'interface/type',
                'inheritance': match.group(2).strip() if match.group(2) else '',
                'file': rel_path
            })
        
        # Find classes and components
        classes = re.finditer(r'(?:class|const)\s+(\w+)(?:\s*(?:extends|implements)\s+([^{]+))?(?:\s*=\s*(?:styled|React\.memo|React\.forwardRef))?\s*[{<]', content)
        for match in classes:
            structure['patterns']['class_patterns'].append({
                'name': match.group(1),
                'type': 'class/component',
                'inheritance': match.group(2).strip() if match.group(2) else '',
                'file': rel_path
            })
        
        # Find functions and hooks
        functions = re.finditer(r'(?:function|const)\s+(\w+)\s*(?:<[^>]+>)?\s*(?:=\s*)?(?:async\s*)?\((.*?)\)(?:\s*:\s*([^{=]+))?', content)
        for match in functions:
            name = match.group(1)
            is_hook = name.startsWith('use') and name[3].isUpper()
            structure['patterns']['function_patterns'].append({
                'name': name,
                'type': 'hook' if is_hook else 'function',
                'parameters': match.group(2),
                'return_type': match.group(3).strip() if match.group(3) else None,
                'file': rel_path
            })
        
        # Find JSX components in TSX files
        if rel_path.endswith('.tsx'):
            components = re.finditer(r'<(\w+)(?:\s+[^>]*)?>', content)
            for match in components:
                component_name = match.group(1)
                if component_name[0].isupper():  # Custom components start with uppercase
                    structure['patterns']['class_patterns'].append({
                        'name': component_name,
                        'type': 'jsx_component',
                        'file': rel_path
                    }) 