/**
 * Build hierarchy for department and position data
 */
function buildHierarchy(departments, positions) {
    if (!departments || !departments.length) {
        return null;
    }

    // Create position map for quick lookup
    const positionMap = new Map(positions.map(p => [p.id, p]));

    // Find the root department (no parent_id and no parent_position_id)
    const rootDept = departments.find(dept => 
        !dept.parent_id && (!dept.parent_position_id || !positionMap.has(dept.parent_position_id))
    );
    
    if (!rootDept) {
        return null;
    }

    // Create root node
    const rootNode = {
        id: `dept_${rootDept.id}`,
        name: rootDept.name,
        title: '{% trans "Department" %}',
        type: 'department',
        level: 0,
        children: [],
        nodeType: 'department',
        department_id: rootDept.id
    };

    // Build department hierarchy
    buildDepartmentHierarchy(rootNode, departments, positions, positionMap);

    // Organize departments to alternate left-right (Christmas tree pattern)
    organizeTreeStructure(rootNode);

    return rootNode;
}

/**
 * Recursively build department hierarchy
 */
function buildDepartmentHierarchy(parentNode, allDepartments, allPositions, positionMap) {
    // Find child departments (with parent_id, not parent_position_id)
    const childDepts = allDepartments.filter(dept => 
        dept.parent_id === parentNode.department_id &&
        !dept.parent_position_id
    );
    
    // Find positions in this department (with department_id, not parent_position_id)
    const deptPositions = allPositions.filter(pos => 
        pos.department_id === parentNode.department_id &&
        !pos.parent_position_id
    );
    
    // Add positions as children first
    deptPositions.forEach(pos => {
        const posNode = {
            id: `pos_${pos.id}`,
            name: pos.name,
            title: '{% trans "Position" %}',
            type: 'position',
            level: parentNode.level + 1,
            children: [],
            nodeType: 'position',
            position_id: pos.id,
            department_id: parentNode.department_id
        };
        
        // Recursively build children for this position (child positions and departments)
        buildPositionHierarchy(posNode, allDepartments, allPositions, positionMap);
        
        parentNode.children.push(posNode);
    });
    
    // Then add departments
    childDepts.forEach(dept => {
        const deptNode = {
            id: `dept_${dept.id}`,
            name: dept.name,
            title: '{% trans "Department" %}',
            type: 'department',
            level: parentNode.level + 1,
            children: [],
            nodeType: 'department',
            department_id: dept.id
        };
        
        // Recursively build children for this department
        buildDepartmentHierarchy(deptNode, allDepartments, allPositions, positionMap);
        
        // Add department to parent's children
        parentNode.children.push(deptNode);
    });
}

/**
 * Recursively build position hierarchy (for positions with parent_position_id)
 */
function buildPositionHierarchy(parentPosNode, allDepartments, allPositions, positionMap) {
    // Find child positions (with parent_position_id pointing to this position)
    const childPositions = allPositions.filter(pos => 
        pos.parent_position_id === parentPosNode.position_id &&
        pos.id !== parentPosNode.position_id
    );
    
    // Find child departments (with parent_position_id pointing to this position)
    const childDepts = allDepartments.filter(dept => 
        dept.parent_position_id === parentPosNode.position_id
    );
    
    // Add child positions
    childPositions.forEach(pos => {
        const posNode = {
            id: `pos_${pos.id}`,
            name: pos.name,
            title: '{% trans "Position" %}',
            type: 'position',
            level: parentPosNode.level + 1,
            children: [],
            nodeType: 'position',
            position_id: pos.id,
            department_id: pos.department_id
        };
        
        // Recursively build children for this position
        buildPositionHierarchy(posNode, allDepartments, allPositions, positionMap);
        
        parentPosNode.children.push(posNode);
    });
    
    // Add child departments
    childDepts.forEach(dept => {
        const deptNode = {
            id: `dept_${dept.id}`,
            name: dept.name,
            title: '{% trans "Department" %}',
            type: 'department',
            level: parentPosNode.level + 1,
            children: [],
            nodeType: 'department',
            department_id: dept.id
        };
        
        // Recursively build children for this department
        buildDepartmentHierarchy(deptNode, allDepartments, allPositions, positionMap);
        
        parentPosNode.children.push(deptNode);
    });
}

/**
 * Organize nodes into a tree-like structure with alternating left-right pattern
 */
function organizeTreeStructure(node, isEvenLevel = true) {
    if (!node.children || node.children.length === 0) {
        return;
    }
    
    // Sort children alternating left and right
    // We'll mark odd-indexed nodes to appear on left, even-indexed on right
    node.children.forEach((child, index) => {
        child.isLeftSide = isEvenLevel ? (index % 2 !== 0) : (index % 2 === 0);
        child.visualLevel = node.level + 1;
        
        // Recursively organize child's children
        organizeTreeStructure(child, !isEvenLevel);
    });
}

/**
 * Create custom node with additional styling based on node type and position
 */
function createCustomNode($node, data) {
    // Add node type class
    if (data.type) {
        $node.addClass(data.type);
    }
    
    // Add tree position classes for alternating left-right pattern
    if (data.isLeftSide) {
        $node.addClass('tree-left-node');
    } else {
        $node.addClass('tree-right-node');
    }
    
    // Visual level affects vertical position
    if (data.visualLevel) {
        $node.attr('data-level', data.visualLevel);
    }
    
    // Add custom action buttons
    $node.find('.content').append(
        `<div class="node-actions mt-2">
            <button class="btn btn-sm btn-outline-primary node-edit-btn" title="{% trans 'Edit' %}">
                <i class="bi bi-pencil-square"></i>
            </button>
            <button class="btn btn-sm btn-outline-danger node-delete-btn" title="{% trans 'Delete' %}">
                <i class="bi bi-trash"></i>
            </button>
         </div>`
    );
    
    // Store node data
    $node.data('nodeData', data);
    
    // Add event handlers
    $node.find('.node-edit-btn').on('click', function(e) {
        e.stopPropagation();
        handleNodeEdit($node, data);
    });
    
    $node.find('.node-delete-btn').on('click', function(e) {
        e.stopPropagation();
        handleNodeDelete($node, data);
    });
} 