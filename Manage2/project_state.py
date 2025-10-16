"""
Project State Manager
=====================

Manages multiple A3 projects with their own databases and states.
Each project contains:
- Project name (Project 1, Project 2, etc.)
- Canvas state (nodes, viewport, annotations)
- Selected files
- Modified flag for save warnings

Uses the centralized ProjectDatabase for all persistence operations.
"""

import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime

# Import the centralized database manager
from .project_database import ProjectDatabase


@dataclass
class ProjectData:
    """Data for a single A3 project"""
    name: str
    id: int
    created_at: str
    modified_at: str
    is_modified: bool
    selected_files: List[str]
    canvas_state: Dict[str, Any]  # Stores nodes, viewport, annotations
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'ProjectData':
        """Create ProjectData from dictionary"""
        return ProjectData(**data)


class ProjectStateManager:
    """
    Manages multiple A3 projects and their states.
    Uses ProjectDatabase for all persistence operations.
    
    Features:
    - Create/delete projects
    - Track active project
    - Save/load project states
    - Detect unsaved changes
    """
    
    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize project state manager
        
        Args:
            storage_path: Path to store project data (defaults to Manage2/projects.json)
        """
        # Initialize the database manager (but don't use it anymore)
        self.database = ProjectDatabase(storage_path)
        
        self.projects: Dict[int, ProjectData] = {}
        self.active_project_id: Optional[int] = None
        self.next_project_id: int = 1
        
        # DON'T load projects from database automatically
        # Projects will only be loaded from .mndoc files via Load A3 Project
        print(f"[ProjectState] Initialized with empty project list (no auto-load from projects.json)")
    
    def create_project(self, name: Optional[str] = None, auto_save: bool = False) -> ProjectData:
        """
        Create a new project
        
        Args:
            name: Project name (defaults to "Project N")
            auto_save: Whether to auto-save to database (default False)
            
        Returns:
            Created ProjectData
        """
        if name is None:
            name = f"Project {self.next_project_id}"
        
        now = datetime.now().isoformat()
        project = ProjectData(
            name=name,
            id=self.next_project_id,
            created_at=now,
            modified_at=now,
            is_modified=True,  # Mark as modified since it's not saved yet
            selected_files=[],
            canvas_state={}
        )
        
        self.projects[self.next_project_id] = project
        self.next_project_id += 1
        
        return project
    
    def delete_project(self, project_id: int, save: bool = True) -> bool:
        """
        Delete a project
        
        Args:
            project_id: ID of project to delete
            save: Whether to save to database after deletion (default True)
            
        Returns:
            True if deleted, False if not found
        """
        if project_id not in self.projects:
            return False
        
        del self.projects[project_id]
        
        # If active project was deleted, clear active
        if self.active_project_id == project_id:
            self.active_project_id = None
        
        # Save after deleting if requested
        if save:
            self.save_projects()
        
        return True
    
    def get_project(self, project_id: int) -> Optional[ProjectData]:
        """Get project by ID"""
        return self.projects.get(project_id)
    
    def get_active_project(self) -> Optional[ProjectData]:
        """Get currently active project"""
        if self.active_project_id is None:
            return None
        return self.projects.get(self.active_project_id)
    
    def set_active_project(self, project_id: int) -> bool:
        """
        Set active project
        
        Args:
            project_id: ID of project to activate
            
        Returns:
            True if set, False if project not found
        """
        if project_id not in self.projects:
            return False
        
        self.active_project_id = project_id
        return True
    
    def get_all_projects(self) -> List[ProjectData]:
        """Get all projects sorted by ID"""
        return sorted(self.projects.values(), key=lambda p: p.id)
    
    def update_project_canvas(self, project_id: int, canvas_state: Dict[str, Any]) -> bool:
        """
        Update project's canvas state
        
        Args:
            project_id: ID of project to update
            canvas_state: New canvas state
            
        Returns:
            True if updated, False if project not found
        """
        project = self.get_project(project_id)
        if project is None:
            return False
        
        project.canvas_state = canvas_state
        project.modified_at = datetime.now().isoformat()
        project.is_modified = True
        
        return True
    
    def update_project_files(self, project_id: int, selected_files: List[str]) -> bool:
        """
        Update project's selected files
        
        Args:
            project_id: ID of project to update
            selected_files: List of file paths
            
        Returns:
            True if updated, False if project not found
        """
        project = self.get_project(project_id)
        if project is None:
            return False
        
        project.selected_files = selected_files
        project.modified_at = datetime.now().isoformat()
        project.is_modified = True
        
        return True
    
    def mark_project_saved(self, project_id: int) -> bool:
        """
        Mark project as saved (clear modified flag)
        
        Args:
            project_id: ID of project
            
        Returns:
            True if marked, False if project not found
        """
        project = self.get_project(project_id)
        if project is None:
            return False
        
        project.is_modified = False
        return True
    
    def has_unsaved_changes(self, project_id: Optional[int] = None) -> bool:
        """
        Check if project has unsaved changes
        
        Args:
            project_id: ID of project (defaults to active project)
            
        Returns:
            True if has unsaved changes
        """
        if project_id is None:
            project_id = self.active_project_id
        
        if project_id is None:
            return False
        
        project = self.get_project(project_id)
        if project is None:
            return False
        
        return project.is_modified
    
    def save_projects(self) -> None:
        """
        DEPRECATED: Projects are now saved to .mndoc files, not projects.json
        This method is kept for compatibility but does nothing.
        """
        print(f"[ProjectState] save_projects() called but ignored - projects are saved to .mndoc files")
        # Don't save to projects.json anymore
        pass
    
    def load_projects(self) -> None:
        """
        DEPRECATED: Projects are now loaded from .mndoc files, not projects.json
        This method is kept for compatibility but does nothing.
        """
        print(f"[ProjectState] load_projects() called but ignored - projects are loaded from .mndoc files")
        # Don't load from projects.json anymore
        # Projects will be loaded when user clicks "Load A3 Project"
        pass
    
    def export_project(self, project_id: int, export_path: str) -> bool:
        """
        Export a single project to a .a3proj file
        
        Args:
            project_id: ID of project to export
            export_path: Path to save exported project
            
        Returns:
            True if exported successfully
        """
        project = self.get_project(project_id)
        if project is None:
            return False
        
        try:
            # Build current database structure
            data = {
                'next_project_id': self.next_project_id,
                'active_project_id': self.active_project_id,
                'projects': {
                    str(pid): p.to_dict() 
                    for pid, p in self.projects.items()
                }
            }
            
            # Use database manager to export
            return self.database.export_project(data, project_id, export_path)
            
        except Exception as e:
            print(f"[ProjectState] Error exporting project: {e}")
            return False
    
    def import_project(self, import_path: str) -> Optional[ProjectData]:
        """
        Import a project from a .a3proj file
        
        Args:
            import_path: Path to .a3proj file
            
        Returns:
            Imported ProjectData or None if failed
        """
        try:
            # Build current database structure
            data = {
                'next_project_id': self.next_project_id,
                'active_project_id': self.active_project_id,
                'projects': {
                    str(pid): p.to_dict() 
                    for pid, p in self.projects.items()
                }
            }
            
            # Use database manager to import
            new_id = self.database.import_project(data, import_path)
            
            if new_id is None:
                return None
            
            # Update our state
            self.next_project_id = data['next_project_id']
            
            # Reload projects to get the imported one
            self.load_projects()
            
            return self.get_project(new_id)
            
        except Exception as e:
            print(f"[ProjectState] Error importing project: {e}")
            import traceback
            traceback.print_exc()
            return None
