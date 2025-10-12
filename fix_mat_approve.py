#!/usr/bin/env python3
"""Fix the approveEdit function in OvrigaMateriellaNote (MAT) component"""

file_path = 'frontend/src/components/Noter.tsx'

# Read the file
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find and replace lines 1615-1622 (the setState calls in approveEdit)
# Line numbers are 0-indexed in the array
old_lines_start = 1614  # Line 1615 in 1-indexed
old_lines_end = 1622    # Line 1623 in 1-indexed

new_code = """    const newCommittedValues = { ...committedValues, ...editedValues };
    const newCommittedPrevValues = { ...committedPrevValues, ...editedPrevValues };
    
    setCommittedValues(newCommittedValues);
    setCommittedPrevValues(newCommittedPrevValues);
    setEditedValues({});
    setEditedPrevValues({});
    setMismatch({ open: false, deltaCur: 0, deltaPrev: 0 });
    setShowValidationMessage(false);
    setIsEditing(false);
    setToggle?.(false);
    
    // Update items with new values and bubble up to parent
    const updatedItems = items.map(item => {
      if (!item.variable_name) return item;
      const newCurrent = newCommittedValues[item.variable_name];
      const newPrevious = newCommittedPrevValues[item.variable_name];
      return {
        ...item,
        current_amount: newCurrent !== undefined ? newCurrent : item.current_amount,
        previous_amount: newPrevious !== undefined ? newPrevious : item.previous_amount,
      };
    });
    
    console.log('✅ [MAT-APPROVE] Updating items with edits:', { 
      editedCount: Object.keys(editedValues).length + Object.keys(editedPrevValues).length,
      sampleEdit: Object.keys(editedValues)[0]
    });
    onItemsUpdate?.(updatedItems);
"""

# Replace lines
lines[old_lines_start:old_lines_end+1] = [new_code + '\n']

# Write back
with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print(f"✅ Fixed approveEdit in OvrigaMateriellaNote (lines {old_lines_start+1}-{old_lines_end+1})")

