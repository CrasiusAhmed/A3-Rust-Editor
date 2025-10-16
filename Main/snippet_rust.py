"""
Rust Snippet Expansion System
Provides multi-phase snippet expansion for Rust code constructs.

Supported snippets:
- fn: Function template with name, parameters, return type, and body
- async: Async function template
- struct: Struct definition template
- impl: Implementation block template
- enum: Enum definition template
- #derive: Derive attribute with parentheses
- let: Variable declaration
- if: If statement with optional else-if and else
- ifl: If-let statement
"""

from PySide6.QtGui import QTextCursor, QColor
from PySide6.QtWidgets import QTextEdit

# Import additional snippet methods from snippet_rust2 and snippet_rust3
try:
    from . import snippet_rust2
    from . import snippet_rust3
except ImportError:
    import snippet_rust2
    import snippet_rust3


class RustSnippetManager:
    """
    Manages snippet expansion for Rust code constructs.
    Handles multi-phase expansion with Tab navigation and Escape cancellation.
    """
    
    def __init__(self, editor):
        """
        Initialize the snippet manager.
        
        Args:
            editor: The code editor instance (QPlainTextEdit)
        """
        self.editor = editor
        self.snippet_active = False
        self.snippet_stage = 0
        self.snippet_positions = {}
        self.snippet_trigger = None
        
        # Connect to text changes to detect if snippet was deleted
        self.editor.textChanged.connect(self._check_snippet_validity)
        
        # Derive trait autocomplete mappings
        self.derive_traits = {
            'Debug': 'Debug',
            'Clone': 'Clone',
            'Copy': 'Copy',
            'PartialEq': 'PartialEq',
            'Eq': 'Eq',
            'PartialOrd': 'PartialOrd',
            'Ord': 'Ord',
            'Hash': 'Hash',
            'Default': 'Default',
            'Serialize': 'Serialize',
            'Deserialize': 'Deserialize',
        }
        
        # Lowercase shortcuts for derive traits
        self.derive_shortcuts = {
            'debug': 'Debug',
            'd': 'Debug',
            'clone': 'Clone',
            'cl': 'Clone',
            'copy': 'Copy',
            'co': 'Copy',
            'partialeq': 'PartialEq',
            'peq': 'PartialEq',
            'eq': 'Eq',
            'partialord': 'PartialOrd',
            'pord': 'PartialOrd',
            'ord': 'Ord',
            'hash': 'Hash',
            'h': 'Hash',
            'default': 'Default',
            'def': 'Default',
            'serialize': 'Serialize',
            'ser': 'Serialize',
            'deserialize': 'Deserialize',
            'de': 'Deserialize',
        }
        
        # Allow attribute autocomplete mappings
        self.allow_lints = {
            'dead_code': 'dead_code',
            'unused_variables': 'unused_variables',
            'unused_imports': 'unused_imports',
            'unused_mut': 'unused_mut',
            'non_snake_case': 'non_snake_case',
            'non_camel_case_types': 'non_camel_case_types',
            'non_upper_case_globals': 'non_upper_case_globals',
            'clippy::all': 'clippy::all',
            'clippy::needless_return': 'clippy::needless_return',
            'clippy::redundant_field_names': 'clippy::redundant_field_names',
        }
        
        # Shortcuts for allow lints (including partial matches)
        self.allow_shortcuts = {
            # dead_code
            'd': 'dead_code',
            'de': 'dead_code',
            'dea': 'dead_code',
            'dead': 'dead_code',
            'dc': 'dead_code',
            # unused_variables
            'u': 'unused_variables',
            'un': 'unused_variables',
            'unu': 'unused_variables',
            'unus': 'unused_variables',
            'unuse': 'unused_variables',
            'unused': 'unused_variables',
            'uv': 'unused_variables',
            'var': 'unused_variables',
            'vari': 'unused_variables',
            # unused_imports
            'i': 'unused_imports',
            'im': 'unused_imports',
            'imp': 'unused_imports',
            'impo': 'unused_imports',
            'impor': 'unused_imports',
            'import': 'unused_imports',
            'imports': 'unused_imports',
            'ui': 'unused_imports',
            # unused_mut
            'm': 'unused_mut',
            'mu': 'unused_mut',
            'mut': 'unused_mut',
            'um': 'unused_mut',
            # non_snake_case
            's': 'non_snake_case',
            'sn': 'non_snake_case',
            'sna': 'non_snake_case',
            'snak': 'non_snake_case',
            'snake': 'non_snake_case',
            # non_camel_case_types
            'c': 'non_camel_case_types',
            'ca': 'non_camel_case_types',
            'cam': 'non_camel_case_types',
            'came': 'non_camel_case_types',
            'camel': 'non_camel_case_types',
            # non_upper_case_globals
            'up': 'non_upper_case_globals',
            'upp': 'non_upper_case_globals',
            'uppe': 'non_upper_case_globals',
            'upper': 'non_upper_case_globals',
            # clippy::all
            'cl': 'clippy::all',
            'cli': 'clippy::all',
            'clip': 'clippy::all',
            'clipp': 'clippy::all',
            'clippy': 'clippy::all',
            # clippy::needless_return
            'n': 'clippy::needless_return',
            'ne': 'clippy::needless_return',
            'nee': 'clippy::needless_return',
            'need': 'clippy::needless_return',
            'needl': 'clippy::needless_return',
            'needle': 'clippy::needless_return',
            'needles': 'clippy::needless_return',
            'needless': 'clippy::needless_return',
            # clippy::redundant_field_names
            'r': 'clippy::redundant_field_names',
            're': 'clippy::redundant_field_names',
            'red': 'clippy::redundant_field_names',
            'redu': 'clippy::redundant_field_names',
            'redun': 'clippy::redundant_field_names',
            'redund': 'clippy::redundant_field_names',
            'redunda': 'clippy::redundant_field_names',
            'redundan': 'clippy::redundant_field_names',
            'redundant': 'clippy::redundant_field_names',
        }
        
        # Cfg attribute autocomplete mappings
        self.cfg_options = {
            'target_os = "windows"': 'target_os = "windows"',
            'target_os = "linux"': 'target_os = "linux"',
            'target_os = "macos"': 'target_os = "macos"',
            'target_os = "android"': 'target_os = "android"',
            'target_os = "ios"': 'target_os = "ios"',
            'target_os = "freebsd"': 'target_os = "freebsd"',
            'unix': 'unix',
            'windows': 'windows',
            'target_arch = "x86"': 'target_arch = "x86"',
            'target_arch = "x86_64"': 'target_arch = "x86_64"',
            'target_arch = "arm"': 'target_arch = "arm"',
            'target_arch = "aarch64"': 'target_arch = "aarch64"',
            'target_arch = "wasm32"': 'target_arch = "wasm32"',
            'debug_assertions': 'debug_assertions',
            'not(debug_assertions)': 'not(debug_assertions)',
            'test': 'test',
            'feature = ""': 'feature = ""',
            'all()': 'all()',
            'any()': 'any()',
            'not()': 'not()',
        }
        
        # Shortcuts for cfg options (including partial matches)
        self.cfg_shortcuts = {
            # Windows
            'w': 'target_os = "windows"',
            'wi': 'target_os = "windows"',
            'win': 'target_os = "windows"',
            'wind': 'target_os = "windows"',
            'windo': 'target_os = "windows"',
            'window': 'target_os = "windows"',
            'windows': 'target_os = "windows"',
            # Linux
            'l': 'target_os = "linux"',
            'li': 'target_os = "linux"',
            'lin': 'target_os = "linux"',
            'linu': 'target_os = "linux"',
            'linux': 'target_os = "linux"',
            # macOS
            'm': 'target_os = "macos"',
            'ma': 'target_os = "macos"',
            'mac': 'target_os = "macos"',
            'maco': 'target_os = "macos"',
            'macos': 'target_os = "macos"',
            # Android
            'a': 'target_os = "android"',
            'an': 'target_os = "android"',
            'and': 'target_os = "android"',
            'andr': 'target_os = "android"',
            'andro': 'target_os = "android"',
            'androi': 'target_os = "android"',
            'android': 'target_os = "android"',
            # iOS
            'i': 'target_os = "ios"',
            'io': 'target_os = "ios"',
            'ios': 'target_os = "ios"',
            # FreeBSD
            'f': 'target_os = "freebsd"',
            'fr': 'target_os = "freebsd"',
            'fre': 'target_os = "freebsd"',
            'free': 'target_os = "freebsd"',
            'freeb': 'target_os = "freebsd"',
            'freebs': 'target_os = "freebsd"',
            'freebsd': 'target_os = "freebsd"',
            # Unix
            'u': 'unix',
            'un': 'unix',
            'uni': 'unix',
            'unix': 'unix',
            # x86
            'x': 'target_arch = "x86"',
            'x8': 'target_arch = "x86"',
            'x86': 'target_arch = "x86"',
            # x86_64
            'x6': 'target_arch = "x86_64"',
            'x64': 'target_arch = "x86_64"',
            'x86_': 'target_arch = "x86_64"',
            'x86_6': 'target_arch = "x86_64"',
            'x86_64': 'target_arch = "x86_64"',
            # ARM
            'ar': 'target_arch = "arm"',
            'arm': 'target_arch = "arm"',
            # aarch64
            'aa': 'target_arch = "aarch64"',
            'aac': 'target_arch = "aarch64"',
            'aach': 'target_arch = "aarch64"',
            'aarch': 'target_arch = "aarch64"',
            'aarch6': 'target_arch = "aarch64"',
            'aarch64': 'target_arch = "aarch64"',
            # WASM
            'wa': 'target_arch = "wasm32"',
            'was': 'target_arch = "wasm32"',
            'wasm': 'target_arch = "wasm32"',
            'wasm3': 'target_arch = "wasm32"',
            'wasm32': 'target_arch = "wasm32"',
            # Debug
            'd': 'debug_assertions',
            'de': 'debug_assertions',
            'deb': 'debug_assertions',
            'debu': 'debug_assertions',
            'debug': 'debug_assertions',
            # Release
            'r': 'not(debug_assertions)',
            're': 'not(debug_assertions)',
            'rel': 'not(debug_assertions)',
            'rele': 'not(debug_assertions)',
            'relea': 'not(debug_assertions)',
            'releas': 'not(debug_assertions)',
            'release': 'not(debug_assertions)',
            # Test
            't': 'test',
            'te': 'test',
            'tes': 'test',
            'test': 'test',
            # Feature
            'fe': 'feature = ""',
            'fea': 'feature = ""',
            'feat': 'feature = ""',
            'featu': 'feature = ""',
            'featur': 'feature = ""',
            'feature': 'feature = ""',
            # Combinators
            'al': 'all()',
            'all': 'all()',
            'an': 'any()',
            'any': 'any()',
            'n': 'not()',
            'no': 'not()',
            'not': 'not()',
        }
        
        # Test attribute options
        self.test_options = {
            'ignore': 'ignore',
            'should_panic': 'should_panic',
            'should_panic(expected = "")': 'should_panic(expected = "")',
        }
        
        # Shortcuts for test options (including partial matches)
        self.test_shortcuts = {
            # ignore
            'i': 'ignore',
            'ig': 'ignore',
            'ign': 'ignore',
            'igno': 'ignore',
            'ignor': 'ignore',
            'ignore': 'ignore',
            # should_panic
            's': 'should_panic',
            'sh': 'should_panic',
            'sho': 'should_panic',
            'shou': 'should_panic',
            'shoul': 'should_panic',
            'should': 'should_panic',
            'p': 'should_panic',
            'pa': 'should_panic',
            'pan': 'should_panic',
            'pani': 'should_panic',
            'panic': 'should_panic',
            'sp': 'should_panic',
            # should_panic(expected = "")
            'e': 'should_panic(expected = "")',
            'ex': 'should_panic(expected = "")',
            'exp': 'should_panic(expected = "")',
            'expe': 'should_panic(expected = "")',
            'expec': 'should_panic(expected = "")',
            'expect': 'should_panic(expected = "")',
            'expecte': 'should_panic(expected = "")',
            'expected': 'should_panic(expected = "")',
        }
        
        # Dynamically attach additional snippet methods from snippet_rust2
        self._attach_additional_snippets()
    
    def _attach_additional_snippets(self):
        """
        Attach additional snippet expansion methods from snippet_rust2 and snippet_rust3 modules.
        This allows us to keep the codebase modular and avoid having a single massive file.
        """
        import types
        
        # List of methods to import from snippet_rust2 (control flow: let, if, ifl, mod)
        methods_from_rust2 = [
            '_expand_let_snippet',
            '_expand_if_snippet',
            '_expand_ifl_snippet',
            '_expand_mod_snippet',
            '_next_stage_let',
            '_next_stage_if',
            '_next_stage_ifl',
            '_next_stage_mod',
            '_cancel_if',
            '_cancel_ifl',
            '_cancel_mod',
        ]
        
        # List of methods to import from snippet_rust3 (loops: for, while, loop, match, trait, type)
        methods_from_rust3 = [
            '_expand_for_snippet',
            '_next_stage_for',
            '_cancel_for',
            '_expand_while_snippet',
            '_next_stage_while',
            '_cancel_while',
            '_expand_loop_snippet',
            '_next_stage_loop',
            '_cancel_loop',
            '_expand_match_snippet',
            '_next_stage_match',
            '_cancel_match',
            '_expand_trait_snippet',
            '_next_stage_trait',
            '_cancel_trait',
            '_expand_type_snippet',
            '_next_stage_type',
            '_cancel_type',
        ]
        
        # Dynamically attach methods from snippet_rust2
        for method_name in methods_from_rust2:
            if hasattr(snippet_rust2, method_name):
                method = getattr(snippet_rust2, method_name)
                setattr(self, method_name, types.MethodType(method, self))
        
        # Dynamically attach methods from snippet_rust3
        for method_name in methods_from_rust3:
            if hasattr(snippet_rust3, method_name):
                method = getattr(snippet_rust3, method_name)
                setattr(self, method_name, types.MethodType(method, self))
    
    def try_trigger_snippet(self, word_start, word):
        """
        Try to trigger a snippet expansion based on the word before cursor.
        
        Args:
            word_start: Absolute position where the word starts
            word: The word to check for snippet trigger
            
        Returns:
            bool: True if a snippet was triggered, False otherwise
        """
        if not word:
            return False
        
        # Disable snippets when multi-cursor is active
        if hasattr(self.editor, 'multi') and self.editor.multi and self.editor.multi.has_multi():
            return False
        
        # Check if word starts with # for attributes
        if word.startswith('#'):
            # Remove the # to get the actual word
            actual_word = word[1:]
            if actual_word == 'derive':
                self._expand_derive_snippet(word_start, len(word))
                return True
            elif actual_word == 'allow':
                self._expand_allow_snippet(word_start, len(word))
                return True
            elif actual_word == 'cfg':
                self._expand_cfg_snippet(word_start, len(word))
                return True
            elif actual_word == 'test':
                self._expand_test_snippet(word_start, len(word))
                return True
        
        # Check for use statements
        if word == 'use':
            self._expand_use_snippet(word_start, len(word), 'std')
            return True
        elif word == 'usec':
            self._expand_use_snippet(word_start, len(word), 'crate')
            return True
        elif word == 'uses':
            self._expand_use_snippet(word_start, len(word), 'super')
            return True
        
        # Check for let statement
        if word == 'let':
            self._expand_let_snippet(word_start, len(word))
            return True
        
        # Check for if statements
        if word == 'if':
            self._expand_if_snippet(word_start, len(word))
            return True
        elif word == 'ifl':
            self._expand_ifl_snippet(word_start, len(word))
            return True
        
        # Check for loop statements
        if word == 'for':
            self._expand_for_snippet(word_start, len(word))
            return True
        elif word == 'while':
            self._expand_while_snippet(word_start, len(word))
            return True
        elif word == 'loop':
            self._expand_loop_snippet(word_start, len(word))
            return True
        elif word == 'match':
            self._expand_match_snippet(word_start, len(word))
            return True
        
        # Check for trait definition
        if word == 'trait':
            self._expand_trait_snippet(word_start, len(word))
            return True
        
        # Check for mod definition
        if word == 'mod':
            self._expand_mod_snippet(word_start, len(word))
            return True
        
        # Check for type alias
        if word == 'type':
            self._expand_type_snippet(word_start, len(word))
            return True
        
        if word == 'fn':
            self._expand_fn_snippet(word_start, len(word))
            return True
        elif word == 'async':
            self._expand_async_snippet(word_start, len(word))
            return True
        elif word == 'struct':
            self._expand_struct_snippet(word_start, len(word))
            return True
        elif word == 'impl':
            self._expand_impl_snippet(word_start, len(word))
            return True
        elif word == 'enum':
            self._expand_enum_snippet(word_start, len(word))
            return True
        
        return False
    
    def next_stage(self):
        """Move to the next stage of snippet expansion."""
        if not self.snippet_active:
            return
        
        self.snippet_stage += 1
        
        # Handle use snippets (use, usec, uses)
        if self.snippet_trigger in ['use_std', 'use_crate', 'use_super']:
            # Phase 1+: User typed something after ::, now add another ::
            cursor = self.editor.textCursor()
            
            # Find the use statement's semicolon on the SAME LINE
            # Get the current line
            block = cursor.block()
            line_start = block.position()
            line_text = block.text()
            
            # Find semicolon in the current line
            semicolon_in_line = line_text.find(';')
            if semicolon_in_line != -1:
                # Calculate absolute position of the semicolon
                semicolon_pos = line_start + semicolon_in_line
                
                # Insert :: before the semicolon
                cursor.setPosition(semicolon_pos)
                cursor.insertText('::')
                # Move cursor after the newly inserted ::
                cursor.setPosition(semicolon_pos + 2)
                self.editor.setTextCursor(cursor)
                # Increment stage to track how many :: we've added
                # Stage 0 = initial (use std::;)
                # Stage 1 = first expansion (use std::io::;)
                # Stage 2+ = further expansions
            return
        
        # Handle attribute snippets with autocomplete (derive, allow, cfg, test)
        if self.snippet_trigger in ['derive', 'allow', 'cfg', 'test']:
            # Try to autocomplete the current word inside the attribute
            autocomplete_method = getattr(self, f'_try_{self.snippet_trigger}_autocomplete', None)
            if autocomplete_method and autocomplete_method():
                # Autocomplete succeeded, stay in the same stage
                self.snippet_stage -= 1
                return
            
            # No autocomplete, finish the snippet
            if self.snippet_stage >= 1:
                self.finish()
            return
        
        # Handle let snippet (delegated)
        if self.snippet_trigger == 'let':
            if hasattr(self, '_next_stage_let'):
                self._next_stage_let()
            return
        
        # Handle if snippet (delegated)
        if self.snippet_trigger == 'if':
            if hasattr(self, '_next_stage_if'):
                self._next_stage_if()
            return
        
        # Handle ifl snippet (delegated)
        if self.snippet_trigger == 'ifl':
            if hasattr(self, '_next_stage_ifl'):
                self._next_stage_ifl()
            return
        
        # Handle for snippet (delegated)
        if self.snippet_trigger == 'for':
            if hasattr(self, '_next_stage_for'):
                self._next_stage_for()
            return
        
        # Handle while snippet (delegated)
        if self.snippet_trigger == 'while':
            if hasattr(self, '_next_stage_while'):
                self._next_stage_while()
            return
        
        # Handle loop snippet (delegated)
        if self.snippet_trigger == 'loop':
            if hasattr(self, '_next_stage_loop'):
                self._next_stage_loop()
            return
        
        # Handle match snippet (delegated)
        if self.snippet_trigger == 'match':
            if hasattr(self, '_next_stage_match'):
                self._next_stage_match()
            return
        
        # Handle trait snippet (delegated)
        if self.snippet_trigger == 'trait':
            if hasattr(self, '_next_stage_trait'):
                self._next_stage_trait()
            return
        
        # Handle mod snippet (delegated)
        if self.snippet_trigger == 'mod':
            if hasattr(self, '_next_stage_mod'):
                self._next_stage_mod()
            return
        
        # Handle type snippet (delegated)
        if self.snippet_trigger == 'type':
            if hasattr(self, '_next_stage_type'):
                self._next_stage_type()
            return
        
        # Check if this is a simple 2-stage snippet (struct, impl, enum)
        if self.snippet_trigger in ['struct', 'impl', 'enum']:
            if self.snippet_stage >= 2:
                self.finish()
                return
            # Stage 1: Move to body
            if self.snippet_stage == 1:
                # Recalculate body position dynamically
                cursor = self.editor.textCursor()
                current_text = self.editor.toPlainText()
                
                # Find the opening brace from the start position
                start_pos = self.snippet_positions[0][0]
                # Search backwards to find the keyword (struct/impl/enum)
                search_start = max(0, start_pos - 20)
                search_text = current_text[search_start:]
                
                # Find the opening brace
                brace_pos = search_text.find('{')
                if brace_pos != -1:
                    body_start = search_start + brace_pos + 1
                    # Skip newline
                    if body_start < len(current_text) and current_text[body_start] == '\n':
                        body_start += 1
                    # Skip indentation
                    while body_start < len(current_text) and current_text[body_start] in ' \t':
                        body_start += 1
                    
                    cursor.setPosition(body_start)
                    self.editor.setTextCursor(cursor)
                    self._highlight_snippet_stage()
            return
        
        # For fn and async snippets (4 stages)
        if self.snippet_stage >= 4:
            self.finish()
            return
        
        cursor = self.editor.textCursor()
        current_text = self.editor.toPlainText()
        
        if self.snippet_stage == 1:
            # Stage 1: Parameters
            fn_start = self.snippet_positions[0][0] - 3
            search_text = current_text[fn_start:]
            paren_pos = search_text.find('(')
            if paren_pos != -1:
                params_start = fn_start + paren_pos + 1
                close_paren_pos = search_text.find(')', paren_pos)
                if close_paren_pos != -1:
                    params_end = fn_start + close_paren_pos
                    self.snippet_positions[1] = (params_start, params_end)
                    cursor.setPosition(params_start)
                    self.editor.setTextCursor(cursor)
                    if params_end > params_start:
                        cursor.setPosition(params_end, QTextCursor.KeepAnchor)
                        self.editor.setTextCursor(cursor)
        
        elif self.snippet_stage == 2:
            # Stage 2: Return type (add -> if not present)
            fn_start = self.snippet_positions[0][0] - 3
            search_text = current_text[fn_start:]
            close_paren_pos = search_text.find(')')
            brace_pos = search_text.find('{')
            
            if close_paren_pos != -1 and brace_pos != -1:
                # Check if -> already exists
                between_paren_and_brace = search_text[close_paren_pos:brace_pos]
                if '->' not in between_paren_and_brace:
                    # Insert " -> " after the closing parenthesis
                    insert_pos = fn_start + close_paren_pos + 1
                    cursor.setPosition(insert_pos)
                    cursor.insertText(' -> ')
                    # Update current_text after insertion
                    current_text = self.editor.toPlainText()
                    search_text = current_text[fn_start:]
                
                # Find position after ->
                arrow_pos = search_text.find('->')
                if arrow_pos != -1:
                    return_type_start = fn_start + arrow_pos + 3  # After "-> "
                    # Find the position before {
                    brace_pos = search_text.find('{', arrow_pos)
                    if brace_pos != -1:
                        return_type_end = fn_start + brace_pos
                        # Trim whitespace
                        while return_type_end > return_type_start and current_text[return_type_end - 1] in ' \t':
                            return_type_end -= 1
                        
                        self.snippet_positions[2] = (return_type_start, return_type_end)
                        cursor.setPosition(return_type_start)
                        self.editor.setTextCursor(cursor)
                        if return_type_end > return_type_start:
                            cursor.setPosition(return_type_end, QTextCursor.KeepAnchor)
                            self.editor.setTextCursor(cursor)
        
        elif self.snippet_stage == 3:
            # Stage 3: Function body
            fn_start = self.snippet_positions[0][0] - 3
            search_text = current_text[fn_start:]
            brace_pos = search_text.find('{')
            if brace_pos != -1:
                # Find position after opening brace
                body_start = fn_start + brace_pos + 1
                
                # Skip the newline after {
                if body_start < len(current_text) and current_text[body_start] == '\n':
                    body_start += 1
                
                # Skip the indentation (4 spaces)
                while body_start < len(current_text) and current_text[body_start] in ' \t':
                    body_start += 1
                
                # Position cursor at the indented line (between { and })
                cursor.setPosition(body_start)
                self.editor.setTextCursor(cursor)
        
        self._highlight_snippet_stage()
    
    def confirm_stage(self):
        """Confirm the current stage and move to next."""
        if not self.snippet_active:
            return
        
        # For simple 2-stage snippets (struct, impl, enum), pressing Enter at stage 0 should move to body
        if self.snippet_trigger in ['struct', 'impl', 'enum']:
            if self.snippet_stage == 0:
                # Move to stage 1 (body)
                self.next_stage()
                return
        
        # For other snippets, just advance to next stage
        self.next_stage()
    
    def cancel(self):
        """Cancel the snippet expansion."""
        if not self.snippet_active:
            return
        
        # Handle if snippet (delegated)
        if self.snippet_trigger == 'if':
            if hasattr(self, '_cancel_if'):
                self._cancel_if()
            return
        
        # Handle ifl snippet (delegated)
        if self.snippet_trigger == 'ifl':
            if hasattr(self, '_cancel_ifl'):
                self._cancel_ifl()
            return
        
        # Handle for snippet (delegated)
        if self.snippet_trigger == 'for':
            if hasattr(self, '_cancel_for'):
                self._cancel_for()
            return
        
        # Handle while snippet (delegated)
        if self.snippet_trigger == 'while':
            if hasattr(self, '_cancel_while'):
                self._cancel_while()
            return
        
        # Handle loop snippet (delegated)
        if self.snippet_trigger == 'loop':
            if hasattr(self, '_cancel_loop'):
                self._cancel_loop()
            return
        
        # Handle match snippet (delegated)
        if self.snippet_trigger == 'match':
            if hasattr(self, '_cancel_match'):
                self._cancel_match()
            return
        
        # Handle use snippets specially
        if self.snippet_trigger in ['use_std', 'use_crate', 'use_super']:
            if self.snippet_stage == 0:
                # Phase 1 (initial): Just finish, keep "use std::;"
                self.finish()
                return
            else:
                # Phase 2+: Remove the last :: that was added
                cursor = self.editor.textCursor()
                
                # Get the current line
                block = cursor.block()
                line_start = block.position()
                line_text = block.text()
                
                # Find semicolon in the current line
                semicolon_in_line = line_text.find(';')
                if semicolon_in_line != -1:
                    # Calculate absolute position of the semicolon
                    semicolon_pos = line_start + semicolon_in_line
                    
                    # Check if there's a :: right before the semicolon
                    if semicolon_in_line >= 2 and line_text[semicolon_in_line-2:semicolon_in_line] == '::':
                        # Remove the ::
                        cursor.setPosition(semicolon_pos - 2)
                        cursor.setPosition(semicolon_pos, QTextCursor.KeepAnchor)
                        cursor.removeSelectedText()
                        # Move cursor before the semicolon
                        cursor.setPosition(semicolon_pos - 2)
                        self.editor.setTextCursor(cursor)
                
                # Go back one stage
                self.snippet_stage -= 1
                if self.snippet_stage < 0:
                    self.snippet_stage = 0
                return
        
        if self.snippet_stage == 0:
            # Stage 0: Delete entire snippet
            cursor = self.editor.textCursor()
            
            # Handle attribute snippets specially (derive, allow, cfg, test)
            if self.snippet_trigger in ['derive', 'allow', 'cfg', 'test']:
                # Delete the entire attribute
                start = self.snippet_positions.get('start')
                end = self.snippet_positions.get('end')
                if start is not None and end is not None:
                    cursor.setPosition(start)
                    cursor.setPosition(end, QTextCursor.KeepAnchor)
                    cursor.removeSelectedText()
                    self.editor.setTextCursor(cursor)
                self.finish()
                return
            
            # Handle other snippets (fn, struct, impl, enum)
            fn_start = self.snippet_positions[0][0] - 3
            current_text = self.editor.toPlainText()
            search_text = current_text[fn_start:]
            brace_pos = search_text.find('}')
            if brace_pos != -1:
                fn_end = fn_start + brace_pos + 1
                cursor.setPosition(fn_start)
                cursor.setPosition(fn_end, QTextCursor.KeepAnchor)
                cursor.removeSelectedText()
                self.editor.setTextCursor(cursor)
            self.finish()
        
        elif self.snippet_stage == 1:
            # Stage 1 (parameters): Skip to return type stage
            self.next_stage()
        
        elif self.snippet_stage == 2:
            # Stage 2 (return type): Remove " -> " and skip to body
            cursor = self.editor.textCursor()
            current_text = self.editor.toPlainText()
            fn_start = self.snippet_positions[0][0] - 3
            search_text = current_text[fn_start:]
            
            # Find the " -> " part
            close_paren_pos = search_text.find(')')
            arrow_pos = search_text.find('->', close_paren_pos)
            brace_pos = search_text.find('{', close_paren_pos)
            
            if arrow_pos != -1 and brace_pos != -1:
                # Remove everything between ) and {, then add single space
                remove_start = fn_start + close_paren_pos + 1
                remove_end = fn_start + brace_pos
                
                # Delete the " -> returntype " part
                cursor.setPosition(remove_start)
                cursor.setPosition(remove_end, QTextCursor.KeepAnchor)
                cursor.removeSelectedText()
                
                # Add single space between ) and {
                cursor.insertText(' ')
                
                # Now move to stage 3 (body)
                self.snippet_stage = 2  # Set to 2 so next_stage will go to 3
                self.next_stage()
        
        else:
            # Other stages: Just finish the snippet
            self.finish()
    
    def finish(self):
        """Finish the snippet expansion and clean up."""
        self.snippet_active = False
        self.snippet_stage = 0
        self.snippet_positions = {}
        self.snippet_trigger = None
        self.editor.setExtraSelections([])
        cursor = self.editor.textCursor()
        cursor.clearSelection()
        self.editor.setTextCursor(cursor)
    
    def is_active(self):
        """Check if a snippet is currently active."""
        return self.snippet_active
    
    def _check_snippet_validity(self):
        """Check if the active snippet still exists in the document. If not, clear it."""
        if not self.snippet_active:
            return
        
        try:
            current_text = self.editor.toPlainText()
            
            # For use snippets, check if the use statement still exists
            if self.snippet_trigger in ['use_std', 'use_crate', 'use_super']:
                start = self.snippet_positions.get('start')
                end = self.snippet_positions.get('end')
                
                if start is not None and end is not None:
                    # Check if the positions are still valid
                    if start >= len(current_text) or end > len(current_text):
                        # Positions are out of bounds, snippet was deleted
                        self.finish()
                        return
                    
                    # Check if the snippet text still exists at those positions
                    snippet_text = current_text[start:end]
                    use_type = self.snippet_trigger.split('_')[1]  # Extract 'std', 'crate', or 'super'
                    expected_pattern = f'use {use_type}::'
                    
                    if not snippet_text.startswith(expected_pattern):
                        # Snippet was deleted or modified beyond recognition
                        self.finish()
                        return
            
            # For attribute snippets (derive, allow, cfg, test)
            elif self.snippet_trigger in ['derive', 'allow', 'cfg', 'test']:
                start = self.snippet_positions.get('start')
                end = self.snippet_positions.get('end')
                
                if start is not None and end is not None:
                    if start >= len(current_text) or end > len(current_text):
                        self.finish()
                        return
                    
                    snippet_text = current_text[start:end]
                    if not snippet_text.startswith(f'#[{self.snippet_trigger}'):
                        self.finish()
                        return
            
            # For loop snippets (for, while, loop, match, let, if, ifl)
            elif self.snippet_trigger in ['for', 'while', 'loop', 'match', 'let', 'if', 'ifl']:
                start = self.snippet_positions.get('start')
                
                if start is not None:
                    # Check if the start position is still valid
                    if start >= len(current_text):
                        self.finish()
                        return
                    
                    # Check if the snippet keyword still exists near the start position
                    search_start = max(0, start - 10)
                    search_end = min(len(current_text), start + 50)
                    search_text = current_text[search_start:search_end]
                    
                    # Map trigger to keyword
                    keyword_map = {
                        'for': 'for ',
                        'while': 'while ',
                        'loop': 'loop ',
                        'match': 'match ',
                        'let': 'let ',
                        'if': 'if ',
                        'ifl': 'if let '
                    }
                    
                    keyword = keyword_map.get(self.snippet_trigger, '')
                    if keyword and keyword not in search_text:
                        # Keyword was deleted, finish the snippet
                        self.finish()
                        return
            
            # For other snippets (fn, struct, impl, enum, trait, async)
            elif self.snippet_trigger in ['fn', 'async', 'struct', 'impl', 'enum', 'trait']:
                # Check if the first position is still valid
                if 0 in self.snippet_positions:
                    pos_start, pos_end = self.snippet_positions[0]
                    
                    if pos_start >= len(current_text) or pos_end > len(current_text):
                        self.finish()
                        return
        
        except Exception:
            # If any error occurs, just finish the snippet to be safe
            self.finish()
    
    def _find_matching_brace(self, text, start_pos):
        """
        Find the position of the closing brace that matches the opening brace at start_pos.
        
        Args:
            text: The text to search in
            start_pos: Position of the opening brace
            
        Returns:
            Position of the matching closing brace, or -1 if not found
        """
        if start_pos >= len(text) or text[start_pos] != '{':
            return -1
        
        brace_count = 0
        pos = start_pos
        
        while pos < len(text):
            if text[pos] == '{':
                brace_count += 1
            elif text[pos] == '}':
                brace_count -= 1
                if brace_count == 0:
                    return pos
            pos += 1
        
        return -1
    
    def _highlight_snippet_stage(self):
        """Highlight the current snippet stage."""
        extra_selections = []
        selection = QTextEdit.ExtraSelection()
        highlight_color = QColor(70, 130, 180, 50)
        selection.format.setBackground(highlight_color)
        cursor = self.editor.textCursor()
        selection.cursor = cursor
        extra_selections.append(selection)
        self.editor.setExtraSelections(extra_selections)
    
    def _expand_fn_snippet(self, start_pos, length):
        """Expand 'fn' into a function template."""
        cursor = QTextCursor(self.editor.document())
        cursor.setPosition(start_pos)
        cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, length)
        cursor.removeSelectedText()
        
        # Get the current indentation level
        current_text = self.editor.toPlainText()
        line_start = start_pos
        while line_start > 0 and current_text[line_start - 1] not in '\n':
            line_start -= 1
        indent = ''
        pos = line_start
        while pos < start_pos and current_text[pos] in ' \t':
            indent += current_text[pos]
            pos += 1
        
        # Create template with proper indentation
        template = f"fn name() {{\n{indent}    \n{indent}}}"
        cursor.insertText(template)
        name_start = start_pos + 3
        name_end = name_start + 4
        self.snippet_positions = {
            0: (name_start, name_end),
            1: (name_end + 1, name_end + 1),
            2: (start_pos + len(f"fn name() {{\n{indent}    "), start_pos + len(f"fn name() {{\n{indent}    "))
        }
        self.snippet_active = True
        self.snippet_stage = 0
        self.snippet_trigger = 'fn'
        cursor.setPosition(name_start)
        cursor.setPosition(name_end, QTextCursor.KeepAnchor)
        self.editor.setTextCursor(cursor)
        self._highlight_snippet_stage()
    
    def _expand_async_snippet(self, start_pos, length):
        """Expand 'async' into an async function template."""
        cursor = QTextCursor(self.editor.document())
        cursor.setPosition(start_pos)
        cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, length)
        cursor.removeSelectedText()
        
        # Get the current indentation level
        current_text = self.editor.toPlainText()
        line_start = start_pos
        while line_start > 0 and current_text[line_start - 1] not in '\n':
            line_start -= 1
        indent = ''
        pos = line_start
        while pos < start_pos and current_text[pos] in ' \t':
            indent += current_text[pos]
            pos += 1
        
        # Create template with proper indentation
        template = f"async fn name() {{\n{indent}    \n{indent}}}"
        cursor.insertText(template)
        # Position after "async fn " (9 characters)
        name_start = start_pos + 9
        name_end = name_start + 4  # "name"
        self.snippet_positions = {
            0: (name_start, name_end),
            1: (name_end + 1, name_end + 1),
            2: (start_pos + len(f"async fn name() {{\n{indent}    "), start_pos + len(f"async fn name() {{\n{indent}    "))
        }
        self.snippet_active = True
        self.snippet_stage = 0
        self.snippet_trigger = 'async'
        cursor.setPosition(name_start)
        cursor.setPosition(name_end, QTextCursor.KeepAnchor)
        self.editor.setTextCursor(cursor)
        self._highlight_snippet_stage()
    
    def _expand_struct_snippet(self, start_pos, length):
        """Expand 'struct' into a struct definition template."""
        cursor = QTextCursor(self.editor.document())
        cursor.setPosition(start_pos)
        cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, length)
        cursor.removeSelectedText()
        
        # Get the current indentation level
        current_text = self.editor.toPlainText()
        line_start = start_pos
        while line_start > 0 and current_text[line_start - 1] not in '\n':
            line_start -= 1
        indent = ''
        pos = line_start
        while pos < start_pos and current_text[pos] in ' \t':
            indent += current_text[pos]
            pos += 1
        
        # Create template with proper indentation
        template = f"struct Name {{\n{indent}    \n{indent}}}"
        cursor.insertText(template)
        
        # Get current text to find actual positions
        current_text = self.editor.toPlainText()
        
        # Find "struct " starting from start_pos
        search_start = max(0, start_pos - 10)
        search_text = current_text[search_start:]
        
        struct_pos = search_text.find('struct ')
        if struct_pos != -1:
            actual_start = search_start + struct_pos
            name_start = actual_start + 7  # After "struct "
            name_end = name_start + 4  # "Name"
            
            # Find the opening brace and calculate body position
            brace_pos = search_text.find('{', struct_pos)
            if brace_pos != -1:
                body_start = search_start + brace_pos + 1  # After {
                # Skip newline
                if body_start < len(current_text) and current_text[body_start] == '\n':
                    body_start += 1
                # Skip indentation
                while body_start < len(current_text) and current_text[body_start] in ' \t':
                    body_start += 1
                
                self.snippet_positions = {0: (name_start, name_end), 1: (body_start, body_start)}
                self.snippet_active = True
                self.snippet_stage = 0
                self.snippet_trigger = 'struct'
                cursor.setPosition(name_start)
                cursor.setPosition(name_end, QTextCursor.KeepAnchor)
                self.editor.setTextCursor(cursor)
                self._highlight_snippet_stage()
    
    def _expand_impl_snippet(self, start_pos, length):
        """Expand 'impl' into an impl block template."""
        cursor = QTextCursor(self.editor.document())
        cursor.setPosition(start_pos)
        cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, length)
        cursor.removeSelectedText()
        
        # Get the current indentation level
        current_text = self.editor.toPlainText()
        line_start = start_pos
        while line_start > 0 and current_text[line_start - 1] not in '\n':
            line_start -= 1
        indent = ''
        pos = line_start
        while pos < start_pos and current_text[pos] in ' \t':
            indent += current_text[pos]
            pos += 1
        
        # Create template with proper indentation
        template = f"impl Name {{\n{indent}    \n{indent}}}"
        cursor.insertText(template)
        
        # Get current text to find actual positions
        current_text = self.editor.toPlainText()
        
        # Find "impl " starting from start_pos
        search_start = max(0, start_pos - 10)
        search_text = current_text[search_start:]
        
        impl_pos = search_text.find('impl ')
        if impl_pos != -1:
            actual_start = search_start + impl_pos
            name_start = actual_start + 5  # After "impl "
            name_end = name_start + 4  # "Name"
            
            # Find the opening brace and calculate body position
            brace_pos = search_text.find('{', impl_pos)
            if brace_pos != -1:
                body_start = search_start + brace_pos + 1  # After {
                # Skip newline
                if body_start < len(current_text) and current_text[body_start] == '\n':
                    body_start += 1
                # Skip indentation
                while body_start < len(current_text) and current_text[body_start] in ' \t':
                    body_start += 1
                
                self.snippet_positions = {0: (name_start, name_end), 1: (body_start, body_start)}
                self.snippet_active = True
                self.snippet_stage = 0
                self.snippet_trigger = 'impl'
                cursor.setPosition(name_start)
                cursor.setPosition(name_end, QTextCursor.KeepAnchor)
                self.editor.setTextCursor(cursor)
                self._highlight_snippet_stage()
    
    def _expand_enum_snippet(self, start_pos, length):
        """Expand 'enum' into an enum definition template."""
        cursor = QTextCursor(self.editor.document())
        cursor.setPosition(start_pos)
        cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, length)
        cursor.removeSelectedText()
        
        # Get the current indentation level
        current_text = self.editor.toPlainText()
        line_start = start_pos
        while line_start > 0 and current_text[line_start - 1] not in '\n':
            line_start -= 1
        indent = ''
        pos = line_start
        while pos < start_pos and current_text[pos] in ' \t':
            indent += current_text[pos]
            pos += 1
        
        # Create template with proper indentation
        template = f"enum Name {{\n{indent}    \n{indent}}}"
        cursor.insertText(template)
        
        # Get current text to find actual positions
        current_text = self.editor.toPlainText()
        
        # Find "enum " starting from start_pos
        search_start = max(0, start_pos - 10)
        search_text = current_text[search_start:]
        
        enum_pos = search_text.find('enum ')
        if enum_pos != -1:
            actual_start = search_start + enum_pos
            name_start = actual_start + 5  # After "enum "
            name_end = name_start + 4  # "Name"
            
            # Find the opening brace and calculate body position
            brace_pos = search_text.find('{', enum_pos)
            if brace_pos != -1:
                body_start = search_start + brace_pos + 1  # After {
                # Skip newline
                if body_start < len(current_text) and current_text[body_start] == '\n':
                    body_start += 1
                # Skip indentation
                while body_start < len(current_text) and current_text[body_start] in ' \t':
                    body_start += 1
                
                self.snippet_positions = {0: (name_start, name_end), 1: (body_start, body_start)}
                self.snippet_active = True
                self.snippet_stage = 0
                self.snippet_trigger = 'enum'
                cursor.setPosition(name_start)
                cursor.setPosition(name_end, QTextCursor.KeepAnchor)
                self.editor.setTextCursor(cursor)
                self._highlight_snippet_stage()
    
    def _expand_derive_snippet(self, start_pos, length):
        """
        Expand '#derive' into #[derive()] with immediate expansion.
        Phase 1: Type #derive + Tab → creates #[derive()] immediately
        Cursor moves inside the parentheses
        Tab inside: Autocomplete derive traits (Debug, Clone, etc.)
        Escape: Removes everything
        """
        cursor = QTextCursor(self.editor.document())
        cursor.setPosition(start_pos)
        cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, length)
        cursor.removeSelectedText()
        
        # Insert #[derive()] immediately
        template = "#[derive()]"
        cursor.insertText(template)
        
        # Get current text to find actual positions
        current_text = self.editor.toPlainText()
        
        # Find "#[derive()]" starting from start_pos
        search_start = max(0, start_pos - 10)
        search_text = current_text[search_start:]
        
        derive_pos = search_text.find('#[derive()]')
        if derive_pos != -1:
            actual_start = search_start + derive_pos
            # Position cursor inside the parentheses
            inside_parens_pos = actual_start + 9  # After "#[derive("
            
            # Store positions
            self.snippet_positions = {
                0: (inside_parens_pos, inside_parens_pos),
                'start': actual_start,  # Store start position for deletion
                'end': actual_start + 11  # Store end position (#[derive()] = 11 chars)
            }
            self.snippet_active = True
            self.snippet_stage = 0
            self.snippet_trigger = 'derive'
            
            # Move cursor inside the parentheses
            cursor.setPosition(inside_parens_pos)
            self.editor.setTextCursor(cursor)
            self._highlight_snippet_stage()
    
    def _try_derive_autocomplete(self):
        """
        Try to autocomplete derive traits inside #[derive()].
        Returns True if autocomplete was performed, False otherwise.
        """
        cursor = self.editor.textCursor()
        current_text = self.editor.toPlainText()
        current_pos = cursor.position()
        
        # Find the #[derive(...)] block we're in
        # Search backwards for #[derive(
        search_start = max(0, current_pos - 100)
        search_text = current_text[search_start:current_pos + 50]
        
        # Check if we're inside #[derive()]
        derive_start = search_text.rfind('#[derive(')
        if derive_start == -1:
            return False
        
        # Find the closing parenthesis
        derive_close = search_text.find(')', derive_start)
        if derive_close == -1:
            return False
        
        # Calculate absolute positions
        abs_derive_start = search_start + derive_start + 9  # After "#[derive("
        abs_derive_close = search_start + derive_close
        
        # Check if cursor is inside the parentheses
        if not (abs_derive_start <= current_pos <= abs_derive_close):
            return False
        
        # Get the content inside derive()
        inside_content = current_text[abs_derive_start:abs_derive_close]
        
        # Find the current word being typed (before cursor)
        words_before_cursor = current_text[abs_derive_start:current_pos]
        
        # Split by comma to get individual traits
        traits = [t.strip() for t in words_before_cursor.split(',')]
        current_word = traits[-1] if traits else ''
        
        # Remove any whitespace
        current_word = current_word.strip()
        
        # If no word is being typed, don't autocomplete
        if not current_word:
            return False
        
        # Try to find a match in shortcuts or full names
        matched_trait = None
        
        # Check shortcuts first (case-insensitive)
        if current_word.lower() in self.derive_shortcuts:
            matched_trait = self.derive_shortcuts[current_word.lower()]
        # Check if it's a partial match of a full trait name
        elif current_word in self.derive_traits:
            matched_trait = self.derive_traits[current_word]
        else:
            # Try fuzzy matching - find traits that start with the typed text
            current_lower = current_word.lower()
            for trait_name in self.derive_traits.values():
                if trait_name.lower().startswith(current_lower):
                    matched_trait = trait_name
                    break
        
        # If we found a match, replace the current word
        if matched_trait:
            # Calculate the start position of the current word
            word_start = current_pos - len(current_word)
            
            # Replace the word
            cursor.setPosition(word_start)
            cursor.setPosition(current_pos, QTextCursor.KeepAnchor)
            cursor.removeSelectedText()
            cursor.insertText(matched_trait)
            
            # DON'T add comma/space here - let the user's keypress do that
            # This way when they press comma or space, it gets inserted naturally
            
            self.editor.setTextCursor(cursor)
            return True
        
        return False
    
    def _expand_allow_snippet(self, start_pos, length):
        """
        Expand '#allow' into #[allow()] with immediate expansion.
        """
        cursor = QTextCursor(self.editor.document())
        cursor.setPosition(start_pos)
        cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, length)
        cursor.removeSelectedText()
        
        # Insert #[allow()] immediately
        template = "#[allow()]"
        cursor.insertText(template)
        
        # Get current text to find actual positions
        current_text = self.editor.toPlainText()
        
        # Find "#[allow()]" starting from start_pos
        search_start = max(0, start_pos - 10)
        search_text = current_text[search_start:]
        
        allow_pos = search_text.find('#[allow()]')
        if allow_pos != -1:
            actual_start = search_start + allow_pos
            # Position cursor inside the parentheses
            inside_parens_pos = actual_start + 8  # After "#[allow("
            
            # Store positions
            self.snippet_positions = {
                0: (inside_parens_pos, inside_parens_pos),
                'start': actual_start,
                'end': actual_start + 10  # #[allow()] = 10 chars
            }
            self.snippet_active = True
            self.snippet_stage = 0
            self.snippet_trigger = 'allow'
            
            # Move cursor inside the parentheses
            cursor.setPosition(inside_parens_pos)
            self.editor.setTextCursor(cursor)
            self._highlight_snippet_stage()
    
    def _try_allow_autocomplete(self):
        """
        Try to autocomplete allow lints inside #[allow()].
        """
        cursor = self.editor.textCursor()
        current_text = self.editor.toPlainText()
        current_pos = cursor.position()
        
        # Find the #[allow(...)] block we're in
        search_start = max(0, current_pos - 100)
        search_text = current_text[search_start:current_pos + 50]
        
        # Check if we're inside #[allow()]
        allow_start = search_text.rfind('#[allow(')
        if allow_start == -1:
            return False
        
        # Find the closing parenthesis
        allow_close = search_text.find(')', allow_start)
        if allow_close == -1:
            return False
        
        # Calculate absolute positions
        abs_allow_start = search_start + allow_start + 8  # After "#[allow("
        abs_allow_close = search_start + allow_close
        
        # Check if cursor is inside the parentheses
        if not (abs_allow_start <= current_pos <= abs_allow_close):
            return False
        
        # Find the current word being typed (before cursor)
        words_before_cursor = current_text[abs_allow_start:current_pos]
        
        # Split by comma to get individual lints
        lints = [t.strip() for t in words_before_cursor.split(',')]
        current_word = lints[-1] if lints else ''
        current_word = current_word.strip()
        
        if not current_word:
            return False
        
        # Try to find a match
        matched_lint = None
        
        # Check shortcuts first
        if current_word.lower() in self.allow_shortcuts:
            matched_lint = self.allow_shortcuts[current_word.lower()]
        elif current_word in self.allow_lints:
            matched_lint = self.allow_lints[current_word]
        else:
            # Fuzzy matching
            current_lower = current_word.lower()
            for lint_name in self.allow_lints.values():
                if lint_name.lower().startswith(current_lower):
                    matched_lint = lint_name
                    break
        
        if matched_lint:
            word_start = current_pos - len(current_word)
            cursor.setPosition(word_start)
            cursor.setPosition(current_pos, QTextCursor.KeepAnchor)
            cursor.removeSelectedText()
            cursor.insertText(matched_lint)
            self.editor.setTextCursor(cursor)
            return True
        
        return False
    
    def _expand_cfg_snippet(self, start_pos, length):
        """
        Expand '#cfg' into #[cfg()] with immediate expansion.
        """
        cursor = QTextCursor(self.editor.document())
        cursor.setPosition(start_pos)
        cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, length)
        cursor.removeSelectedText()
        
        # Insert #[cfg()] immediately
        template = "#[cfg()]"
        cursor.insertText(template)
        
        # Get current text to find actual positions
        current_text = self.editor.toPlainText()
        
        # Find "#[cfg()]" starting from start_pos
        search_start = max(0, start_pos - 10)
        search_text = current_text[search_start:]
        
        cfg_pos = search_text.find('#[cfg()]')
        if cfg_pos != -1:
            actual_start = search_start + cfg_pos
            # Position cursor inside the parentheses
            inside_parens_pos = actual_start + 6  # After "#[cfg("
            
            # Store positions
            self.snippet_positions = {
                0: (inside_parens_pos, inside_parens_pos),
                'start': actual_start,
                'end': actual_start + 8  # #[cfg()] = 8 chars
            }
            self.snippet_active = True
            self.snippet_stage = 0
            self.snippet_trigger = 'cfg'
            
            # Move cursor inside the parentheses
            cursor.setPosition(inside_parens_pos)
            self.editor.setTextCursor(cursor)
            self._highlight_snippet_stage()
    
    def _try_cfg_autocomplete(self):
        """
        Try to autocomplete cfg options inside #[cfg()].
        """
        cursor = self.editor.textCursor()
        current_text = self.editor.toPlainText()
        current_pos = cursor.position()
        
        # Find the #[cfg(...)] block we're in
        search_start = max(0, current_pos - 100)
        search_text = current_text[search_start:current_pos + 50]
        
        # Check if we're inside #[cfg()]
        cfg_start = search_text.rfind('#[cfg(')
        if cfg_start == -1:
            return False
        
        # Find the closing parenthesis
        cfg_close = search_text.find(')', cfg_start)
        if cfg_close == -1:
            return False
        
        # Calculate absolute positions
        abs_cfg_start = search_start + cfg_start + 6  # After "#[cfg("
        abs_cfg_close = search_start + cfg_close
        
        # Check if cursor is inside the parentheses
        if not (abs_cfg_start <= current_pos <= abs_cfg_close):
            return False
        
        # Find the current word being typed (before cursor)
        words_before_cursor = current_text[abs_cfg_start:current_pos]
        
        # Split by comma to get individual options
        options = [t.strip() for t in words_before_cursor.split(',')]
        current_word = options[-1] if options else ''
        current_word = current_word.strip()
        
        if not current_word:
            return False
        
        # Try to find a match
        matched_option = None
        
        # Check shortcuts first
        if current_word.lower() in self.cfg_shortcuts:
            matched_option = self.cfg_shortcuts[current_word.lower()]
        elif current_word in self.cfg_options:
            matched_option = self.cfg_options[current_word]
        else:
            # Fuzzy matching
            current_lower = current_word.lower()
            for option_name in self.cfg_options.values():
                if option_name.lower().startswith(current_lower):
                    matched_option = option_name
                    break
        
        if matched_option:
            word_start = current_pos - len(current_word)
            cursor.setPosition(word_start)
            cursor.setPosition(current_pos, QTextCursor.KeepAnchor)
            cursor.removeSelectedText()
            cursor.insertText(matched_option)
            self.editor.setTextCursor(cursor)
            return True
        
        return False
    
    def _expand_test_snippet(self, start_pos, length):
        """
        Expand '#test' into #[test] with immediate expansion.
        """
        cursor = QTextCursor(self.editor.document())
        cursor.setPosition(start_pos)
        cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, length)
        cursor.removeSelectedText()
        
        # Insert #[test] immediately
        template = "#[test]"
        cursor.insertText(template)
        
        # Get current text to find actual positions
        current_text = self.editor.toPlainText()
        
        # Find "#[test]" starting from start_pos
        search_start = max(0, start_pos - 10)
        search_text = current_text[search_start:]
        
        test_pos = search_text.find('#[test]')
        if test_pos != -1:
            actual_start = search_start + test_pos
            # Position cursor after #[test
            inside_pos = actual_start + 6  # After "#[test"
            
            # Store positions
            self.snippet_positions = {
                0: (inside_pos, inside_pos),
                'start': actual_start,
                'end': actual_start + 7  # #[test] = 7 chars
            }
            self.snippet_active = True
            self.snippet_stage = 0
            self.snippet_trigger = 'test'
            
            # Move cursor after #[test
            cursor.setPosition(inside_pos)
            self.editor.setTextCursor(cursor)
            self._highlight_snippet_stage()
    
    def _try_test_autocomplete(self):
        """
        Try to autocomplete test options - works even after deleting 'test'.
        If 'test' was deleted, just show the option (ignore, should_panic).
        If 'test' is present, show #[test, option].
        """
        cursor = self.editor.textCursor()
        current_text = self.editor.toPlainText()
        current_pos = cursor.position()
        
        # Find the #[...] block we're in
        search_start = max(0, current_pos - 100)
        search_text = current_text[search_start:current_pos + 50]
        
        # Check if we're inside #[...] (could be #[test] or just #[)
        bracket_start = search_text.rfind('#[')
        if bracket_start == -1:
            return False
        
        # Find the closing bracket
        bracket_close = search_text.find(']', bracket_start)
        if bracket_close == -1:
            return False
        
        # Calculate absolute positions
        abs_bracket_start = search_start + bracket_start + 2  # After "#["
        abs_bracket_close = search_start + bracket_close
        
        # Check if cursor is between #[ and ]
        if not (abs_bracket_start <= current_pos <= abs_bracket_close):
            return False
        
        # Get what's typed after #[
        typed_text = current_text[abs_bracket_start:current_pos].strip()
        
        # Check if 'test' is present
        has_test = typed_text.startswith('test')
        
        # Remove 'test' if present (so we can work with just the option)
        if has_test:
            typed_text = typed_text[4:].strip()
            if typed_text.startswith(','):
                typed_text = typed_text[1:].strip()
        
        if not typed_text:
            return False
        
        # Try to find a match
        matched_option = None
        
        # Check shortcuts first
        if typed_text.lower() in self.test_shortcuts:
            matched_option = self.test_shortcuts[typed_text.lower()]
        elif typed_text in self.test_options:
            matched_option = self.test_options[typed_text]
        else:
            # Fuzzy matching
            typed_lower = typed_text.lower()
            for option_name in self.test_options.values():
                if option_name.lower().startswith(typed_lower):
                    matched_option = option_name
                    break
        
        if matched_option:
            # Replace the content
            cursor.setPosition(abs_bracket_start)
            cursor.setPosition(current_pos, QTextCursor.KeepAnchor)
            cursor.removeSelectedText()
            
            if has_test:
                # 'test' is present, add both: test, option
                cursor.insertText(f'test, {matched_option}')
            else:
                # 'test' was deleted, just show the option
                cursor.insertText(matched_option)
            
            self.editor.setTextCursor(cursor)
            return True
        
        return False
    
    def _expand_use_snippet(self, start_pos, length, use_type):
        """
        Expand 'use', 'usec', or 'uses' into use statements with multi-phase navigation.
        
        Phase 1: Creates 'use std::;' (or crate/super) and moves cursor after first ::
        Phase 2: When Tab is pressed, adds another :: before the semicolon
        Escape: Deletes the entire use statement
        
        Args:
            start_pos: Position where the trigger word starts
            length: Length of the trigger word
            use_type: Type of use statement ('std', 'crate', or 'super')
        """
        cursor = QTextCursor(self.editor.document())
        cursor.setPosition(start_pos)
        cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, length)
        cursor.removeSelectedText()
        
        # Create the use statement
        template = f"use {use_type}::;"
        cursor.insertText(template)
        
        # Get current text to find actual positions
        current_text = self.editor.toPlainText()
        
        # Find the use statement we just created
        search_start = max(0, start_pos - 10)
        search_text = current_text[search_start:]
        
        use_pos = search_text.find(f'use {use_type}::;')
        if use_pos != -1:
            actual_start = search_start + use_pos
            # Position cursor after the first ::
            after_double_colon = actual_start + len(f'use {use_type}::')
            
            # Store positions for deletion if needed
            use_end = actual_start + len(f'use {use_type}::;')
            
            self.snippet_positions = {
                0: (after_double_colon, after_double_colon),
                'start': actual_start,
                'end': use_end
            }
            self.snippet_active = True
            self.snippet_stage = 0
            self.snippet_trigger = f'use_{use_type}'
            
            # Move cursor after the ::
            cursor.setPosition(after_double_colon)
            self.editor.setTextCursor(cursor)
            self._highlight_snippet_stage()
    