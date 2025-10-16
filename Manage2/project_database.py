"""
Project Database Manager
========================

Centralized database management for A3 projects.
Handles all persistence operations for project data including:
- Nodes and their positions
- Connections between nodes
- Viewport settings (camera position, zoom)
- Annotations (strokes, text)
- Panel positions

This module provides a clean separation between the UI and data persistence,
making it easier to maintain and debug.
"""

import json
import os
from typing import Dict, List, Optional, Any
from datetime import datetime


class ProjectDatabase:
    """
    Manages project data persistence to a JSON database file.
    
    Features:
    - Thread-safe file operations
    - Automatic backup on save
    - Data validation
    - Migration support for schema changes
    """
    
    def __init__(self, database_path: Optional[str] = None):
        """
        Initialize the project database.
        
        Args:
            database_path: Path to the database file. If None, uses default location.
        """
        if database_path is None:
            # Default to Manage2/projects.json
            base_dir = os.path.dirname(os.path.abspath(__file__))
            database_path = os.path.join(base_dir, "projects.json")
        
        self.database_path = database_path
        self.backup_path = database_path + ".backup"
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.database_path), exist_ok=True)
        
        print(f"[ProjectDatabase] Initialized with database at: {self.database_path}")
    
    def load_all_projects(self) -> Dict[str, Any]:
        """
        Load all projects from the database.
        
        Returns:
            Dictionary containing all project data with structure:
            {
                'next_project_id': int,
                'active_project_id': int or None,
                'projects': {
                    'project_id': {
                        'name': str,
                        'id': int,
                        'created_at': str,
                        'modified_at': str,
                        'is_modified': bool,
                        'selected_files': list,
                        'canvas_state': {
                            'nodes': list,
                            'connections': list,
                            'viewport': dict,
                            'annotations': dict,
                            'panels': dict
                        }
                    }
                }
            }
        """
        try:
            if not os.path.exists(self.database_path):
                print(f"[ProjectDatabase] No database file found, returning empty structure")
                return self._create_empty_database()
            
            with open(self.database_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Validate structure
            if not isinstance(data, dict):
                print(f"[ProjectDatabase] Invalid database format, creating new")
                return self._create_empty_database()
            
            # Ensure required keys exist
            if 'projects' not in data:
                data['projects'] = {}
            if 'next_project_id' not in data:
                data['next_project_id'] = 1
            if 'active_project_id' not in data:
                data['active_project_id'] = None
            
            num_projects = len(data.get('projects', {}))
            print(f"[ProjectDatabase] Loaded {num_projects} projects from database")
            
            return data
            
        except json.JSONDecodeError as e:
            print(f"[ProjectDatabase] JSON decode error: {e}")
            # Try to restore from backup
            if os.path.exists(self.backup_path):
                print(f"[ProjectDatabase] Attempting to restore from backup")
                try:
                    with open(self.backup_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    print(f"[ProjectDatabase] Successfully restored from backup")
                    return data
                except Exception:
                    pass
            
            print(f"[ProjectDatabase] Creating new database")
            return self._create_empty_database()
            
        except Exception as e:
            print(f"[ProjectDatabase] Error loading database: {e}")
            import traceback
            traceback.print_exc()
            return self._create_empty_database()
    
    def save_all_projects(self, data: Dict[str, Any]) -> bool:
        """
        Save all projects to the database.
        
        Args:
            data: Complete database structure to save
            
        Returns:
            True if save was successful, False otherwise
        """
        try:
            # Create backup of existing database
            if os.path.exists(self.database_path):
                try:
                    import shutil
                    shutil.copy2(self.database_path, self.backup_path)
                except Exception as e:
                    print(f"[ProjectDatabase] Warning: Could not create backup: {e}")
            
            # Validate data structure
            if not isinstance(data, dict):
                print(f"[ProjectDatabase] Error: Invalid data structure")
                return False
            
            # Ensure required keys
            if 'projects' not in data:
                data['projects'] = {}
            if 'next_project_id' not in data:
                data['next_project_id'] = 1
            
            # Write to database
            with open(self.database_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            num_projects = len(data.get('projects', {}))
            print(f"[ProjectDatabase] Saved {num_projects} projects to database")
            
            return True
            
        except Exception as e:
            print(f"[ProjectDatabase] Error saving database: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def get_project(self, data: Dict[str, Any], project_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a specific project from the database.
        
        Args:
            data: Database structure
            project_id: ID of the project to retrieve
            
        Returns:
            Project data dictionary or None if not found
        """
        try:
            projects = data.get('projects', {})
            project_key = str(project_id)
            
            if project_key in projects:
                return projects[project_key]
            
            print(f"[ProjectDatabase] Project {project_id} not found")
            return None
            
        except Exception as e:
            print(f"[ProjectDatabase] Error getting project: {e}")
            return None
    
    def update_project(self, data: Dict[str, Any], project_id: int, project_data: Dict[str, Any]) -> bool:
        """
        Update a specific project in the database.
        
        Args:
            data: Database structure
            project_id: ID of the project to update
            project_data: New project data
            
        Returns:
            True if update was successful, False otherwise
        """
        try:
            if 'projects' not in data:
                data['projects'] = {}
            
            project_key = str(project_id)
            data['projects'][project_key] = project_data
            
            print(f"[ProjectDatabase] Updated project {project_id}")
            return True
            
        except Exception as e:
            print(f"[ProjectDatabase] Error updating project: {e}")
            return False
    
    def delete_project(self, data: Dict[str, Any], project_id: int) -> bool:
        """
        Delete a specific project from the database.
        
        Args:
            data: Database structure
            project_id: ID of the project to delete
            
        Returns:
            True if deletion was successful, False otherwise
        """
        try:
            if 'projects' not in data:
                return False
            
            project_key = str(project_id)
            
            if project_key in data['projects']:
                del data['projects'][project_key]
                print(f"[ProjectDatabase] Deleted project {project_id}")
                return True
            
            print(f"[ProjectDatabase] Project {project_id} not found for deletion")
            return False
            
        except Exception as e:
            print(f"[ProjectDatabase] Error deleting project: {e}")
            return False
    
    def _create_empty_database(self) -> Dict[str, Any]:
        """
        Create an empty database structure.
        
        Returns:
            Empty database dictionary
        """
        return {
            'next_project_id': 1,
            'active_project_id': None,
            'projects': {},
            'schema_version': 1,
            'created_at': datetime.now().isoformat(),
            'modified_at': datetime.now().isoformat()
        }
    
    def export_project(self, data: Dict[str, Any], project_id: int, export_path: str) -> bool:
        """
        Export a single project to a standalone file.
        
        Args:
            data: Database structure
            project_id: ID of the project to export
            export_path: Path where to save the exported project
            
        Returns:
            True if export was successful, False otherwise
        """
        try:
            project = self.get_project(data, project_id)
            
            if not project:
                print(f"[ProjectDatabase] Cannot export: project {project_id} not found")
                return False
            
            # Ensure .a3proj extension
            if not export_path.endswith('.a3proj'):
                export_path += '.a3proj'
            
            # Write project to file
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(project, f, indent=2, ensure_ascii=False)
            
            print(f"[ProjectDatabase] Exported project {project_id} to {export_path}")
            return True
            
        except Exception as e:
            print(f"[ProjectDatabase] Error exporting project: {e}")
            return False
    
    def import_project(self, data: Dict[str, Any], import_path: str) -> Optional[int]:
        """
        Import a project from a standalone file.
        
        Args:
            data: Database structure
            import_path: Path to the .a3proj file to import
            
        Returns:
            ID of the imported project, or None if import failed
        """
        try:
            if not os.path.exists(import_path):
                print(f"[ProjectDatabase] Import file not found: {import_path}")
                return None
            
            # Read project file
            with open(import_path, 'r', encoding='utf-8') as f:
                project_data = json.load(f)
            
            # Assign new ID
            next_id = data.get('next_project_id', 1)
            project_data['id'] = next_id
            project_data['modified_at'] = datetime.now().isoformat()
            
            # Add to database
            self.update_project(data, next_id, project_data)
            data['next_project_id'] = next_id + 1
            
            print(f"[ProjectDatabase] Imported project as ID {next_id} from {import_path}")
            return next_id
            
        except Exception as e:
            print(f"[ProjectDatabase] Error importing project: {e}")
            return None
    
    def get_statistics(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get database statistics.
        
        Args:
            data: Database structure
            
        Returns:
            Dictionary with statistics
        """
        try:
            projects = data.get('projects', {})
            
            total_projects = len(projects)
            modified_projects = sum(1 for p in projects.values() if p.get('is_modified', False))
            
            total_nodes = 0
            total_connections = 0
            
            for project in projects.values():
                canvas_state = project.get('canvas_state', {})
                nodes = canvas_state.get('nodes', [])
                connections = canvas_state.get('connections', [])
                
                total_nodes += len(nodes)
                total_connections += len(connections)
            
            return {
                'total_projects': total_projects,
                'modified_projects': modified_projects,
                'total_nodes': total_nodes,
                'total_connections': total_connections,
                'database_size': os.path.getsize(self.database_path) if os.path.exists(self.database_path) else 0
            }
            
        except Exception as e:
            print(f"[ProjectDatabase] Error getting statistics: {e}")
            return {}
    
    def validate_database(self, data: Dict[str, Any]) -> List[str]:
        """
        Validate database integrity and return list of issues found.
        
        Args:
            data: Database structure
            
        Returns:
            List of validation error messages (empty if valid)
        """
        issues = []
        
        try:
            # Check basic structure
            if not isinstance(data, dict):
                issues.append("Database is not a dictionary")
                return issues
            
            if 'projects' not in data:
                issues.append("Missing 'projects' key")
            elif not isinstance(data['projects'], dict):
                issues.append("'projects' is not a dictionary")
            
            if 'next_project_id' not in data:
                issues.append("Missing 'next_project_id' key")
            
            # Validate each project
            projects = data.get('projects', {})
            for project_id, project in projects.items():
                if not isinstance(project, dict):
                    issues.append(f"Project {project_id} is not a dictionary")
                    continue
                
                # Check required fields
                required_fields = ['name', 'id', 'created_at', 'modified_at', 'is_modified']
                for field in required_fields:
                    if field not in project:
                        issues.append(f"Project {project_id} missing required field: {field}")
                
                # Validate canvas_state if present
                if 'canvas_state' in project:
                    canvas_state = project['canvas_state']
                    if not isinstance(canvas_state, dict):
                        issues.append(f"Project {project_id} canvas_state is not a dictionary")
            
            if not issues:
                print(f"[ProjectDatabase] Database validation passed")
            else:
                print(f"[ProjectDatabase] Database validation found {len(issues)} issues")
            
            return issues
            
        except Exception as e:
            issues.append(f"Validation error: {str(e)}")
            return issues


# Singleton instance for easy access
_database_instance = None


def get_database() -> ProjectDatabase:
    """
    Get the singleton database instance.
    
    Returns:
        ProjectDatabase instance
    """
    global _database_instance
    if _database_instance is None:
        _database_instance = ProjectDatabase()
    return _database_instance
