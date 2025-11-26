class PermissionManager:
    """Manage role-based permissions"""
    
    # Define permissions for each role - simplified to only admin and consignor
    ROLE_PERMISSIONS = {
        'admin': {
            'inventory': ['view', 'add', 'edit', 'delete', 'export'],
            'pricing': ['view', 'edit', 'calculate'],
            'ebay': ['view', 'sync', 'export', 'import'],
            'consignment': ['view', 'manage', 'payments'],
            'reports': ['view', 'export'],
            'users': ['view', 'create', 'edit', 'delete'],
            'system': ['configure', 'maintenance']
        },
        'consignor': {
            'inventory': ['view'],
            'pricing': ['view'],
            'ebay': ['view'],
            'consignment': ['view'],
            'reports': ['view'],
            'users': [],
            'system': []
        }
    }
    
    @classmethod
    def has_permission(cls, role: str, module: str, action: str) -> bool:
        """Check if role has permission for specific action in module"""
        if role not in cls.ROLE_PERMISSIONS:
            return False
        
        module_perms = cls.ROLE_PERMISSIONS[role].get(module, [])
        return action in module_perms
    
    @classmethod
    def get_accessible_modules(cls, role: str) -> list:
        """Get list of modules accessible by role"""
        if role not in cls.ROLE_PERMISSIONS:
            return []
        
        return [module for module, perms in cls.ROLE_PERMISSIONS[role].items() if perms]
    
    @classmethod
    def get_role_description(cls, role: str) -> str:
        """Get human-readable role description"""
        descriptions = {
            'admin': 'Full system access including user management',
            'consignor': 'View-only access to consignment data'
        }
        return descriptions.get(role, 'Unknown role')