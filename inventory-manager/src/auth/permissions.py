class PermissionManager:
    """Manage role-based permissions"""
    
    # Define permissions for each role - simplified to only admin and consignor
    ROLE_PERMISSIONS = {
        'admin': {
            'inventory': ['view', 'add', 'edit', 'delete', 'export'],
            'pricing': ['view', 'edit', 'calculate'],
            'ebay': ['view', 'sync', 'export', 'import'],
            'consignment': ['view', 'manage', 'payments'],
            'checkout': ['view', 'process'],
            'reports': ['view', 'export'],
            'users': ['view', 'create', 'edit', 'delete'],
            'system': ['configure', 'maintenance']
        },
        'consignor': {
            'inventory': ['view', 'add'],  # Consignors can view and add
            'pricing': [],
            'ebay': [],
            'consignment': ['view'],  # Consignors can only view (no delete permissions)
            'checkout': [],  # Consignors cannot view checkout
            'reports': [],
            'users': [],
            'system': []
        },
        'demo': {
            'inventory': ['view', 'add'],
            'pricing': [],
            'ebay': [],
            'consignment': ['view'],
            'checkout': [],  # Demo users also cannot view checkout
            'reports': [],
            'users': [],
            'system': []
        }
    }
    
    @classmethod
    def has_permission(cls, role: str, module: str, action: str) -> bool:
        """Check if role has permission for specific action in module"""
        # Handle demo user
        if role == 'demo':
            # Demo user gets same permissions as consignor
            role = 'consignor'
        
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
            'consignor': 'View and add consignment items (cannot delete or checkout)',
            'demo': 'Demo mode with limited functionality for testing'
        }
        return descriptions.get(role, 'Unknown role')