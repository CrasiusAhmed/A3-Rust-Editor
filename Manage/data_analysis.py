"""
Data Analysis Module
Handles Rust code analysis and function dependency extraction
"""

import math
import random
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

# Color palette matching the original design
NODE_COLORS = [
    '#C586C0', '#569CD6', '#9CDCFE', '#4EC9B0',
    '#CE9178', '#B5CEA8', '#DCDCAA', '#D4D4D4',
    '#6A9955', '#D16969', '#D7BA7D', '#569CD6',
    '#9CDCFE', '#4EC9B0', '#CE9178', '#B5CEA8'
]

DARK_THEME = {
    'bg_primary': '#1f1f20',
    'bg_secondary': '#2D2D30', 
    'bg_tertiary': '#3E3E42',
    'text_primary': '#D4D4D4',
    'text_secondary': "#9AA4AF",
    'accent': '#569CD6',
    'success': '#B5CEA8',
    'error': '#D16969',
    'border': '#4A4D51'
}

@dataclass
class FunctionData:
    """Data structure for function information"""
    name: str
    lineno: int
    end_lineno: Optional[int]
    args: List[str]
    docstring: str
    returns: str
    complexity: int
    # Fully qualified name used for stable identity (e.g., Class.method or function)
    qual_name: str = ""
    # Absolute file path for cross-file operations (optional, filled by canvas later)
    file_path: str = ""

class LayoutType(Enum):
    """Layout algorithms for node positioning"""
    CIRCULAR = "circular"
    SPIRAL = "spiral" 
    GRID = "grid"
    FORCE_DIRECTED = "force_directed"

class FunctionAnalyzer:
    """Analyzes Rust code to extract function dependencies"""
    
    def __init__(self):
        self.functions = {}
        self.dependencies = {}
        self.current_code = None
        self.current_file_path = None
        # Cache last known good analysis per absolute file path to keep layout stable on parse errors
        self._last_results_by_file: Dict[str, Dict[str, Any]] = {}
        
    def analyze_code(self, code_content: str, file_path: str = "direct_input") -> Dict[str, Any]:
        """Analyze Rust code and return function data"""
        try:
            self.current_code = code_content
            self.current_file_path = file_path
            # Analyze Rust code
            return self._analyze_rust(code_content, file_path)
        except Exception as e:
            # On parse errors, prefer to use the last known good analysis for this file
            try:
                prev = self._last_results_by_file.get(os.path.abspath(file_path))
            except Exception:
                prev = None
            if prev:
                # Clone prev and attach error fields
                out = dict(prev)
                out['file_path'] = file_path
                out['error'] = str(e)
                return out
            # Return error info
            return {
                'functions': {},
                'dependencies': {},
                'file_path': file_path,
                'total_functions': 0,
                'total_dependencies': 0,
                'total_classes': 0,
                'error': str(e)
            }

    # -------------------- Rust (.rs) analysis --------------------
    def _analyze_rust(self, code: str, file_path: str) -> Dict[str, Any]:
        """Lightweight Rust analyzer to extract functions/methods and build intra-file call graph."""
        import re
        lines = code.split('\n')
        functions: Dict[str, FunctionData] = {}
        dependencies: Dict[str, List[str]] = {}
        func_ranges: Dict[str, tuple] = {}  # name -> (start_line_idx, end_line_idx)
        class_count = 0

        # Track impl context with a stack of (type_name, depth_at_open_brace)
        impl_stack: List[tuple] = []
        brace_depth = 0

        # Precompiled regexes
        re_impl = re.compile(r'^\s*impl\b([^\{]*)\{')
        re_fn = re.compile(r'^\s*(?:pub\s+)?fn\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)\s*(?:->\s*([^\{]+))?')
        re_struct = re.compile(r'^\s*(?:pub\s+)?struct\s+([A-Za-z_][A-Za-z0-9_]*)')
        re_enum = re.compile(r'^\s*(?:pub\s+)?enum\s+([A-Za-z_][A-Za-z0-9_]*)')
        re_trait = re.compile(r'^\s*(?:pub\s+)?trait\s+([A-Za-z_][A-Za-z0-9_]*)')
        re_type = re.compile(r'^\s*(?:pub\s+)?type\s+([A-Za-z_][A-Za-z0-9_]*)\s*=')
        re_const = re.compile(r'^\s*(?:pub\s+)?const\s+([A-Za-z_][A-Za-z0-9_]*)\s*:')
        re_mod = re.compile(r'^\s*(?:pub\s+)?mod\s+([A-Za-z_][A-Za-z0-9_]*)')

        i = 0
        while i < len(lines):
            line = lines[i]
            
            # Detect struct/enum/trait/type/const/mod BEFORE impl
            m_struct = re_struct.match(line)
            m_enum = re_enum.match(line)
            m_trait = re_trait.match(line)
            m_type = re_type.match(line)
            m_const = re_const.match(line)
            m_mod = re_mod.match(line)
            
            if m_struct or m_enum or m_trait or m_type or m_const or m_mod:
                # Determine which one matched
                if m_struct:
                    name = m_struct.group(1)
                elif m_enum:
                    name = m_enum.group(1)
                elif m_trait:
                    name = m_trait.group(1)
                elif m_type:
                    name = m_type.group(1)
                elif m_const:
                    name = m_const.group(1)
                else:  # m_mod
                    name = m_mod.group(1)
                
                doc = self._extract_rust_doc_before(lines, i)
                start_idx = i
                
                # For type and const, they're single line
                if m_type or m_const:
                    end_idx = i
                # For others, find end by tracking braces
                elif '{' in line:
                    j = i
                    k = j
                    local_depth = 0
                    while k < len(lines):
                        local_depth += lines[k].count('{')
                        local_depth -= lines[k].count('}')
                        if local_depth <= 0 and k >= j:
                            break
                        k += 1
                    end_idx = min(k, len(lines) - 1)
                else:
                    # No braces (tuple struct, unit struct, or external mod)
                    end_idx = i
                
                fd = FunctionData(
                    name=name,
                    lineno=start_idx + 1,
                    end_lineno=end_idx + 1,
                    args=[],
                    docstring=doc,
                    returns='',
                    complexity=1,
                    qual_name=name,
                )
                functions[name] = fd
                func_ranges[name] = (start_idx, end_idx)
                dependencies[name] = []
                i = end_idx + 1
                continue
            
            # Detect impl start
            m_impl = re_impl.match(line)
            if m_impl:
                class_count += 1
                ty = (m_impl.group(1) or '').strip()
                # If `impl Trait for Type`, prefer the Type after 'for'
                ty = ty.split(' for ')[-1].strip() if ' for ' in ty else ty
                # Keep only last path segment and strip generics
                if '::' in ty:
                    ty = ty.split('::')[-1].strip()
                ty = re.sub(r'<.*?>', '', ty).strip()
                ty = re.sub(r'[^A-Za-z0-9_].*$', '', ty)
                impl_stack.append((ty or 'impl', brace_depth))
            
            # Detect function/method defs
            m_fn = re_fn.match(line)
            if m_fn:
                name = m_fn.group(1)
                args_str = m_fn.group(2) or ''
                ret_str = (m_fn.group(3) or '').strip()
                # Determine qualified name by impl type if present
                qual_name = name
                if impl_stack and impl_stack[-1][0]:
                    qual_name = f"{impl_stack[-1][0]}::{name}"
                # Collect preceding doc comments (///)
                doc = self._extract_rust_doc_before(lines, i)
                # Extract argument names (skip types)
                args: List[str] = []
                for p in [a.strip() for a in args_str.split(',') if a.strip()]:
                    if p.startswith('self') or p.startswith('&self') or p.startswith('&mut self'):
                        continue
                    nm = p.split(':', 1)[0].strip()
                    if nm:
                        args.append(nm)
                # Find function end by tracking braces starting at the line containing '{'
                start_idx = i
                j = i
                found_open = '{' in line
                while j < len(lines) and not found_open:
                    j += 1
                    found_open = '{' in lines[j]
                k = j
                local_depth = 0
                while k < len(lines):
                    local_depth += lines[k].count('{')
                    local_depth -= lines[k].count('}')
                    if local_depth <= 0 and k >= j:
                        break
                    k += 1
                end_idx = min(k, len(lines) - 1)
                # Extract the source code for this function
                source_code = '\n'.join(lines[start_idx:end_idx+1])
                
                fd = FunctionData(
                    name=name,
                    lineno=start_idx + 1,
                    end_lineno=end_idx + 1,
                    args=args,
                    docstring=doc,
                    returns=ret_str,
                    complexity=self._compute_rust_complexity(lines[start_idx:end_idx+1]),
                    qual_name=qual_name,
                )
                functions[name] = fd
                func_ranges[name] = (start_idx, end_idx)
                dependencies[name] = []
                i = end_idx  # jump after this function
            
            # Update global brace depth and impl stack pops
            brace_depth += line.count('{')
            while impl_stack and brace_depth < impl_stack[-1][1] + 1:
                impl_stack.pop()
            brace_depth -= line.count('}')
            i += 1

        # Second pass: intra-file call dependencies
        # Preserve textual order of calls so layout can pick a deterministic "default" edge.
        known = set(functions.keys())
        combined = re.compile(
            r'(?:\b([A-Za-z_][A-Za-z0-9_]*)\s*\()|(?:\.\s*([A-Za-z_][A-Za-z0-9_]*)\s*\()|(?:::\s*([A-Za-z_][A-Za-z0-9_]*)\s*\()'
        )
        for fname, (s, e) in func_ranges.items():
            body = '\n'.join(lines[s:e+1])
            ordered: List[str] = []
            seen = set()
            for m in combined.finditer(body):
                called = m.group(1) or m.group(2) or m.group(3)
                if not called:
                    continue
                if called in known and called != fname and called not in seen:
                    ordered.append(called)
                    seen.add(called)
            dependencies[fname] = ordered

        # Build result with source_code included for each function
        functions_dict = {}
        for name, func in functions.items():
            func_dict = func.__dict__.copy()
            # Add source_code from the extracted lines
            if name in func_ranges:
                start_idx, end_idx = func_ranges[name]
                func_dict['source_code'] = '\n'.join(lines[start_idx:end_idx+1])
            functions_dict[name] = func_dict
        
        result = {
            'functions': functions_dict,
            'dependencies': dependencies,
            'file_path': file_path,
            'total_functions': len(functions),
            'total_dependencies': sum(len(v) for v in dependencies.values()),
            'total_classes': class_count,
        }
        # Cache last results
        try:
            self._last_results_by_file[os.path.abspath(file_path)] = result
        except Exception:
            pass
        return result

    def _extract_rust_doc_before(self, lines: List[str], idx: int) -> str:
        doc_lines = []
        i = idx - 1
        while i >= 0:
            s = lines[i].strip()
            if s.startswith('///'):
                doc_lines.append(s.lstrip('/').strip())
                i -= 1
            elif not s:
                i -= 1
            else:
                break
        doc_lines.reverse()
        return '\n'.join(doc_lines)

    def _compute_rust_complexity(self, fn_lines: List[str]) -> int:
        text = '\n'.join(fn_lines)
        import re
        # Rough cyclomatic complexity estimation for Rust constructs
        keys = [r'\bif\b', r'\belse\s+if\b', r'\bwhile\b', r'\bfor\b', r'\bloop\b', r'\bmatch\b']
        c = 1
        for k in keys:
            c += len(re.findall(k, text))
        return c

class FunctionNode:
    """Represents a function node in the visualization"""
    
    def __init__(self, function_data: Dict[str, Any], x: float, y: float):
        self.name = function_data['name']
        self.data = function_data
        self.x = x
        self.y = y
        self.original_x = x
        self.original_y = y
        
        # Visual properties
        self.radius = self._calculate_radius()
        self.color = self._get_color()
        self.scale = 1.0
        self.target_scale = 1.0
        self.opacity = 1.0
        self.target_opacity = 1.0
        self.icon_path: Optional[str] = None

        # Blink effect for guiding to main script node
        self.blink_time: float = 0.0      # seconds remaining for blink
        self.blink_phase: float = 0.0     # phase for sine wave
        self.blink_opacity: float = 0.0   # 0..1 used by painter
        
        # State
        self.selected = False
        self.highlighted = False
        self.hovered = False
        
        # Relationships
        self.calls = []
        self.called_by = []
        
        # Animation
        self.pulse_phase = random.random() * math.pi * 2
        
    def _calculate_radius(self) -> float:
        """Calculate node radius based on function properties"""
        base_radius = 30
        complexity_bonus = min(self.data.get('complexity', 1) * 2, 10)
        arg_bonus = min(len(self.data.get('args', [])) * 1.5, 8)
        name_bonus = min(len(self.name) * 0.4, 6)
        return base_radius + complexity_bonus + arg_bonus + name_bonus
    
    def _get_color(self) -> str:
        """Get color based on function name hash"""
        hash_val = 0
        for char in self.name:
            hash_val = ord(char) + ((hash_val << 5) - hash_val)
            hash_val = hash_val & hash_val
        return NODE_COLORS[abs(hash_val) % len(NODE_COLORS)]
    
    def update_animation(self, dt: float):
        """Update animation properties"""
        # Use time-based interpolation for frame-rate independence
        interp_factor = 1.0 - math.exp(-dt * 10.0)  # Smoother damping

        self.scale += (self.target_scale - self.scale) * interp_factor
        self.opacity += (self.target_opacity - self.opacity) * interp_factor
        
        # Keep Y stable to preserve straight forward edges between parent and forward child
        # Always lock Y to original_y; original_y updates when user drags a node.
        self.y = self.original_y

        # Blink animation for guide highlight (approx. 2 Hz)
        if self.blink_time > 0.0:
            self.blink_time = max(0.0, self.blink_time - dt)
            self.blink_phase += 2.0 * math.pi * 2.0 * dt  # 2 cycles per second
            # Smooth 0..1 wave
            self.blink_opacity = 0.5 * (1.0 + math.sin(self.blink_phase))
        else:
            self.blink_opacity = 0.0

class Connection:
    """Represents a connection between two function nodes"""
    
    def __init__(self, from_node: FunctionNode, to_node: FunctionNode):
        self.from_node = from_node
        self.to_node = to_node
        self.highlighted = False
        self.opacity = 0.6
        self.target_opacity = 0.6
        self.flow_offset = random.random() * math.pi * 2
        
    def update_animation(self, dt: float):
        """Update animation properties"""
        # Use time-based interpolation for frame-rate independence
        interp_factor = 1.0 - math.exp(-dt * 6.0)  # Smoother damping
        old_opacity = self.opacity
        old_offset = self.flow_offset
        self.opacity += (self.target_opacity - self.opacity) * interp_factor
        self.flow_offset += 4.0 * dt  # Speed adjusted by delta time
        # Return True if anything changed
        return abs(self.opacity - old_opacity) > 0.001 or abs(self.flow_offset - old_offset) > 0.001
