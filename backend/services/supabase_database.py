"""
Supabase Database Service for direct table operations
"""
import os
from typing import List, Dict, Any, Optional
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class SupabaseDatabase:
    def __init__(self):
        """Initialize Supabase client"""
        self.url = os.getenv('SUPABASE_URL')
        self.key = os.getenv('SUPABASE_ANON_KEY')
        
        if not self.url or not self.key:
            raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY must be set in environment variables")
        
        self.supabase: Client = create_client(self.url, self.key)
    
    def read_table(self, table_name: str, columns: str = "*", filters: Optional[Dict[str, Any]] = None, order_by: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Read data from a table
        
        Args:
            table_name: Name of the table
            columns: Columns to select (default: "*")
            filters: Dictionary of column=value filters
            order_by: Column to order by
            
        Returns:
            List of dictionaries representing rows
        """
        try:
            query = self.supabase.table(table_name).select(columns)
            
            # Apply filters
            if filters:
                for column, value in filters.items():
                    query = query.eq(column, value)
            
            # Apply ordering
            if order_by:
                query = query.order(order_by)
            
            response = query.execute()
            return response.data
            
        except Exception as e:
            print(f"Error reading table {table_name}: {e}")
            return []
    
    def write_table(self, table_name: str, data: List[Dict[str, Any]]) -> bool:
        """
        Insert data into a table
        
        Args:
            table_name: Name of the table
            data: List of dictionaries to insert
            
        Returns:
            True if successful, False otherwise
        """
        try:
            response = self.supabase.table(table_name).insert(data).execute()
            return len(response.data) > 0
            
        except Exception as e:
            print(f"Error writing to table {table_name}: {e}")
            return False
    
    def update_table(self, table_name: str, data: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """
        Update data in a table
        
        Args:
            table_name: Name of the table
            data: Dictionary of column=value updates
            filters: Dictionary of column=value filters for WHERE clause
            
        Returns:
            True if successful, False otherwise
        """
        try:
            query = self.supabase.table(table_name).update(data)
            
            # Apply filters
            for column, value in filters.items():
                query = query.eq(column, value)
            
            response = query.execute()
            return len(response.data) > 0
            
        except Exception as e:
            print(f"Error updating table {table_name}: {e}")
            return False
    
    def delete_from_table(self, table_name: str, filters: Dict[str, Any]) -> bool:
        """
        Delete data from a table
        
        Args:
            table_name: Name of the table
            filters: Dictionary of column=value filters for WHERE clause
            
        Returns:
            True if successful, False otherwise
        """
        try:
            query = self.supabase.table(table_name).delete()
            
            # Apply filters
            for column, value in filters.items():
                query = query.eq(column, value)
            
            response = query.execute()
            return True  # Delete doesn't return data, just check if no error
            
        except Exception as e:
            print(f"Error deleting from table {table_name}: {e}")
            return False
    
    # Specific methods for our tables
    def get_ink2_mappings(self) -> List[Dict[str, Any]]:
        """Get all INK2 variable mappings ordered by row_id"""
        return self.read_table('variable_mapping_ink2', order_by='row_id')
    
    def get_global_variables(self) -> List[Dict[str, Any]]:
        """Get all global variables"""
        return self.read_table('global_variables')
    
    def get_accounts_table(self) -> List[Dict[str, Any]]:
        """Get all accounts"""
        return self.read_table('accounts_table', order_by='account_id')
    
    def add_ink2_mapping(self, variable_name: str, row_title: str, **kwargs) -> bool:
        """
        Add a new INK2 mapping row
        
        Args:
            variable_name: Unique variable name
            row_title: Display title
            **kwargs: Additional column values
            
        Returns:
            True if successful
        """
        # Get next row_id
        existing = self.get_ink2_mappings()
        next_row_id = max([row.get('row_id', 0) for row in existing], default=0) + 1
        
        data = {
            'variable_name': variable_name,
            'row_title': row_title,
            'row_id': next_row_id,
            **kwargs
        }
        
        return self.write_table('variable_mapping_ink2', [data])
    
    def check_ink_sarskild_loneskatt_exists(self) -> bool:
        """Check if INK_sarskild_loneskatt row exists"""
        result = self.read_table('variable_mapping_ink2', filters={'variable_name': 'INK_sarskild_loneskatt'})
        return len(result) > 0
    
    def get_ink_sarskild_loneskatt_mapping(self) -> Optional[Dict[str, Any]]:
        """Get the INK_sarskild_loneskatt mapping if it exists"""
        result = self.read_table('variable_mapping_ink2', filters={'variable_name': 'INK_sarskild_loneskatt'})
        return result[0] if result else None

# Create global instance
db = SupabaseDatabase()
