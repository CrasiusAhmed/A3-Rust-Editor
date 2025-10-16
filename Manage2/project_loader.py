"""
Project Loader Module
=====================

Handles loading project canvas state from saved projects.
Recreates nodes and applies viewport settings.
"""

from typing import Optional


def load_project_canvas(manage_widget, project_state_manager, project_id: int) -> bool:
    """
    Load canvas state for a project
    
    Args:
        manage_widget: The ManageWidget instance containing the canvas
        project_state_manager: The ProjectStateManager instance
        project_id: ID of the project to load
        
    Returns:
        True if loaded successfully, False otherwise
    """
    try:
        # Set as active
        project_state_manager.set_active_project(project_id)
        
        # Get project
        project = project_state_manager.get_project(project_id)
        if not project:
            return False
        
        # CRITICAL: Clear session layouts cache when switching projects
        # This prevents stale panel positions from interfering with the new project
        try:
            if hasattr(manage_widget, '_session_layouts'):
                manage_widget._session_layouts.clear()
                print(f"[ProjectLoader] Cleared session layouts cache")
        except Exception as e:
            print(f"[ProjectLoader] Error clearing session layouts: {e}")
        
        # Clear current canvas
        manage_widget.canvas.clear()
        
        # Load canvas state if available
        if project.canvas_state and project.canvas_state.get('nodes'):
            nodes_to_load = project.canvas_state.get('nodes', [])
            
            # Recreate nodes from saved state
            from Manage.data_analysis import FunctionNode, Connection
            for node_data in nodes_to_load:
                try:
                    # Create node from saved data
                    data = {
                        'name': node_data.get('name', ''),
                        'lineno': node_data.get('lineno', 0),
                        'args': [],
                        'docstring': node_data.get('docstring', ''),
                        'returns': '',
                        'complexity': 1,
                        'file_path': node_data.get('file_path'),
                        'content_type': node_data.get('content_type'),  # Preserve custom content type
                        'source_code': node_data.get('source_code'),  # Restore source code for Rust nodes
                        'type': node_data.get('type'),  # Restore type (Function, Struct, Implementation, etc.)
                    }
                    
                    # Create FunctionNode
                    node = FunctionNode(data, node_data.get('x', 0.0), node_data.get('y', 0.0))
                    
                    # Restore color and icon if available
                    if node_data.get('color'):
                        node.color = node_data['color']
                    if node_data.get('icon_path'):
                        node.icon_path = node_data['icon_path']
                    
                    # Add to canvas
                    manage_widget.canvas.nodes.append(node)
                    
                    # Index the node
                    if hasattr(manage_widget.canvas, '_index_node'):
                        manage_widget.canvas._index_node(node)
                except Exception:
                    pass
            
            # Apply viewport settings and restore connections using SaveLoadManager
            # This handles both viewport and connections in one go
            from Manage.document_io import SaveLoadManager
            save_manager = SaveLoadManager()
            save_manager.apply_to_canvas(manage_widget.canvas, project.canvas_state)
            
            # Update canvas
            manage_widget.canvas.update()
        
        return True
    except Exception:
        return False
