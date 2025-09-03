'use client';

import React, { useMemo, useState, useRef, useCallback, useEffect } from 'react';

interface MenuLink {
  id: number;
  document_id?: string;
  menu_path: string;
  pc_url?: string;
  mobile_url?: string;
  created_by?: string;
  created_at?: string;
  updated_by?: string;
  updated_at?: string;
}

interface TreeNode {
  id: string;
  name: string;
  children: TreeNode[];
  count: number;
  totalCount: number;
  level: number;
  x: number;
  y: number;
  menuLinks: MenuLink[];
  isExpanded: boolean; // 새로운 속성: 노드가 펼쳐져 있는지
  isVisible: boolean;  // 새로운 속성: 노드가 화면에 보이는지
}

interface MenuTreeChartProps {
  menuLinks: MenuLink[];
}

export default function MenuTreeChart({ menuLinks }: MenuTreeChartProps) {
  const [selectedNode, setSelectedNode] = useState<TreeNode | null>(null);
  const [hoveredNode, setHoveredNode] = useState<TreeNode | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [zoomLevel, setZoomLevel] = useState(() => {
    // Calculate initial zoom based on expected node count
    // This will be recalculated when the component renders
    return 1.5; // Temporary default, will be updated
  });
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const dragStartRef = useRef({ x: 0, y: 0, scrollLeft: 0, scrollTop: 0 });

    // Generate hierarchical tree structure from actual menu links data
  const generateCollapsibleTree = (menuLinks: MenuLink[]): TreeNode => {
    let nodeCounter = 0;
    
    // Create root node
    const rootNode: TreeNode = {
      id: `node-${++nodeCounter}`,
      name: '메뉴 루트',
      children: [],
      count: 0,
      totalCount: 0,
      level: 1,
      x: 0,
      y: 0,
      menuLinks: [],
      isExpanded: true,
      isVisible: true
    };

    // Parse menu paths and build tree structure
    const nodeMap = new Map<string, TreeNode>();
    nodeMap.set('', rootNode); // Root path is empty

    menuLinks.forEach(menuLink => {
      const pathParts = menuLink.menu_path.split('^').filter(part => part.trim() !== '');
      let currentPath = '';
      let parentNode = rootNode;

      pathParts.forEach((part, index) => {
        const previousPath = currentPath;
        currentPath = currentPath ? `${currentPath}^${part}` : part;
        const level = index + 2; // Level 1 is root, so menu items start from level 2

        if (!nodeMap.has(currentPath)) {
          // Create new node
          const newNode: TreeNode = {
            id: `node-${++nodeCounter}`,
            name: part,
            children: [],
            count: 0, // Will be calculated later
            totalCount: 0,
            level,
            x: 0,
            y: 0,
            menuLinks: [],
            isExpanded: false,
            isVisible: level <= 2 // Show only root and level 2 initially
          };

          nodeMap.set(currentPath, newNode);
          parentNode.children.push(newNode);
        }

        const currentNode = nodeMap.get(currentPath)!;
        
        // Add menu link to the final node (leaf) - this remains for counting
        if (index === pathParts.length - 1) {
          currentNode.menuLinks.push(menuLink);
          currentNode.count++;
        }

        parentNode = currentNode;
      });
    });

    // After building the tree structure, add menu links to all nodes based on path matching
    menuLinks.forEach(menuLink => {
      const menuPath = menuLink.menu_path;
      
      // For each node, check if the menu link's path starts with the node's path
      nodeMap.forEach((node, nodePath) => {
        if (nodePath === '') return; // Skip root node
        
        // Check if the menu link's path matches or starts with this node's path
        if (menuPath === nodePath || menuPath.startsWith(nodePath + '^')) {
          // Only add if not already present (to avoid duplicates from the leaf node logic above)
          const alreadyExists = node.menuLinks.some(existing => existing.id === menuLink.id);
          if (!alreadyExists) {
            node.menuLinks.push(menuLink);
          }
        }
      });
    });

    // Calculate total counts recursively (bottom-up)
    const calculateTotalCounts = (node: TreeNode): number => {
      if (node.children.length === 0) {
        node.totalCount = node.count;
        return node.totalCount;
      }
      
      let totalCount = node.count;
      node.children.forEach(child => {
        totalCount += calculateTotalCounts(child);
      });
      
      node.totalCount = totalCount;
      return totalCount;
    };

    calculateTotalCounts(rootNode);
    return rootNode;
  };

  // Generate the collapsible tree structure
  const [treeRoot, setTreeRoot] = useState<TreeNode | null>(null);
  const [showLegend, setShowLegend] = useState<boolean>(true);
  const [isClient, setIsClient] = useState(false);

  // Initialize tree only on client side to avoid hydration issues
  useEffect(() => {
    setIsClient(true);
    setTreeRoot(generateCollapsibleTree(menuLinks));
  }, [menuLinks]);
  
  // Fixed sizing for collapsible tree (no need for dynamic sizing since we show fewer nodes)
  const nodeStyle = {
    width: 200,
    height: 80,
    horizontalSpacing: 250,
    verticalSpacing: 120,
    fontSize: {
      title: 16,
      count: 12
    },
    strokeWidth: 2
  };
  
  // Fixed zoom level
  const optimalZoom = 1.0; // 100% zoom is perfect for collapsible tree

  // Legend data for level colors (1-based indexing)
  const legendData = [
    { level: 1, color: '#e53e3e', label: '루트', description: '최상위 노드' },
    { level: 2, color: '#dd6b20', label: '메인 카테고리', description: '주요 메뉴 분류' },
    { level: 3, color: '#d69e2e', label: '서브 카테고리', description: '하위 메뉴 분류' },
    { level: 4, color: '#38a169', label: '세부 카테고리', description: '상세 메뉴 분류' },
    { level: 5, color: '#319795', label: '아이템', description: '개별 메뉴 항목' },
  ];
  
  // Toggle node expansion with sibling collapse
  const toggleNodeExpansion = useCallback((nodeId: string) => {
    const updateNodeRecursively = (node: TreeNode, parentNode?: TreeNode): TreeNode => {
      if (node.id === nodeId) {
        const newExpanded = !node.isExpanded;
        
        // Update children visibility
        const updateChildrenVisibility = (children: TreeNode[], visible: boolean): TreeNode[] => {
          return children.map(child => ({
            ...child,
            isVisible: visible,
            children: updateChildrenVisibility(child.children, visible && child.isExpanded)
          }));
        };
        
        return {
          ...node,
          isExpanded: newExpanded,
          children: updateChildrenVisibility(node.children, newExpanded)
        };
      }
      
      // If this node has the target node as a child, handle sibling collapse
      const hasTargetChild = node.children.some(child => child.id === nodeId);
      if (hasTargetChild) {
        return {
          ...node,
          children: node.children.map(child => {
            if (child.id === nodeId) {
              // This is the target node - expand/collapse it
              const newExpanded = !child.isExpanded;
              const updateChildrenVisibility = (children: TreeNode[], visible: boolean): TreeNode[] => {
                return children.map(grandChild => ({
                  ...grandChild,
                  isVisible: visible,
                  children: updateChildrenVisibility(grandChild.children, visible && grandChild.isExpanded)
                }));
              };
              
              return {
                ...child,
                isExpanded: newExpanded,
                children: updateChildrenVisibility(child.children, newExpanded)
              };
            } else {
              // This is a sibling - collapse it and hide its descendants
              const collapseDescendants = (node: TreeNode): TreeNode => ({
                ...node,
                isExpanded: false,
                isVisible: node.level <= 2, // Keep level 1-2 visible, hide deeper levels
                children: node.children.map(child => ({
                  ...collapseDescendants(child),
                  isVisible: false
                }))
              });
              
              return collapseDescendants(child);
            }
          })
        };
      }
      
      return {
        ...node,
        children: node.children.map(child => updateNodeRecursively(child, node))
      };
    };
    
    setTreeRoot(prevRoot => prevRoot ? updateNodeRecursively(prevRoot) : null);
  }, []);

  // Calculate positions for visible nodes
  const calculateNodePositions = useCallback((root: TreeNode, canvasWidth: number = 1200, canvasHeight: number = 800) => {

    const visibleNodes: TreeNode[] = [];
    const edges: { from: TreeNode; to: TreeNode }[] = [];
    
    // Calculate center position for root (level 1)
    const rootX = canvasWidth / 2;
    const rootY = 100; // Top margin
    
    const traverse = (node: TreeNode, x: number, y: number, parentNode?: TreeNode) => {
      if (node.isVisible) {
        const updatedNode = { ...node, x, y };
        visibleNodes.push(updatedNode);
        
        if (parentNode) {
          edges.push({ from: parentNode, to: updatedNode });
        }
        
        if (node.isExpanded && node.children.length > 0) {
          const visibleChildren = node.children.filter(child => child.isVisible);
          const childrenCount = visibleChildren.length;
          
          if (childrenCount <= 8) {
            // 8개 이하: 기존 방식 (한 줄로 배치)
            const startX = x - ((childrenCount - 1) * nodeStyle.horizontalSpacing) / 2;
            
            let childIndex = 0;
            visibleChildren.forEach(child => {
              const childX = startX + (childIndex * nodeStyle.horizontalSpacing);
              const childY = y + nodeStyle.verticalSpacing;
              traverse(child, childX, childY, updatedNode);
              childIndex++;
            });
          } else {
            // 8개 초과: 4개씩 2줄로 배치
            const itemsPerRow = 4;
            const totalRows = Math.ceil(childrenCount / itemsPerRow);
            const rowHeight = nodeStyle.verticalSpacing;
            const itemSpacing = nodeStyle.horizontalSpacing;
            
            // 첫 번째 줄의 시작 X 위치 계산 (4개 기준으로 중앙 정렬)
            const firstRowStartX = x - ((Math.min(itemsPerRow, childrenCount) - 1) * itemSpacing) / 2;
            
            let childIndex = 0;
            visibleChildren.forEach(child => {
              const row = Math.floor(childIndex / itemsPerRow);
              const col = childIndex % itemsPerRow;
              
              // 각 줄의 시작 X 위치 계산 (해당 줄의 아이템 수 기준으로 중앙 정렬)
              const currentRowItemCount = Math.min(itemsPerRow, childrenCount - row * itemsPerRow);
              const currentRowStartX = x - ((currentRowItemCount - 1) * itemSpacing) / 2;
              
              const childX = currentRowStartX + (col * itemSpacing);
              const childY = y + nodeStyle.verticalSpacing + (row * rowHeight);
              
              traverse(child, childX, childY, updatedNode);
              childIndex++;
            });
          }
        }
      }
    };
    
    // Start from center of canvas
    traverse(root, rootX, rootY);
    
    return { nodes: visibleNodes, edges };
  }, [nodeStyle]);

  // Calculate canvas dimensions first (minimum size)
  const baseDimensions = useMemo(() => ({
    width: 1200,  // Reasonable default width
    height: 800   // Reasonable default height
  }), []);

  const allNodes = useMemo(() => {
    if (!treeRoot) return { nodes: [], edges: [] };
    return calculateNodePositions(treeRoot, baseDimensions.width, baseDimensions.height);
  }, [treeRoot, calculateNodePositions, baseDimensions]);

  const getNodeColor = (node: TreeNode) => {
    // Selected and hovered states
    if (selectedNode?.id === node.id) return '#4299e1';
    if (hoveredNode?.id === node.id) return '#63b3ed';
    
    // Use legend data for consistent colors
    const legendItem = legendData.find(item => item.level === node.level);
    let baseColor = legendItem?.color || '#a0aec0';
    
    // Keep original color for all nodes - no color change for expanded nodes
    // (Removing the darker color effect that was making nodes look different)
    
    return baseColor;
  };

  const getNodeWidth = (node: TreeNode) => {
    return nodeStyle.width; // Fixed width for collapsible tree
  };

  const getNodeHeight = (node: TreeNode) => {
    return nodeStyle.height; // Fixed height for collapsible tree
  };

  // Final canvas dimensions (may be larger than base if tree is big)
  const dimensions = useMemo(() => {
    if (allNodes.nodes.length === 0) return baseDimensions;
    
    const maxWidth = Math.max(...allNodes.nodes.map(node => node.x)) + nodeStyle.width + 100;
    const maxHeight = Math.max(...allNodes.nodes.map(node => node.y)) + nodeStyle.height + 100;
    
    return {
      width: Math.max(baseDimensions.width, maxWidth),
      height: Math.max(baseDimensions.height, maxHeight)
    };
  }, [allNodes.nodes, nodeStyle, baseDimensions]);

  // Drag handlers for panning
  const handleMouseDown = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (!containerRef.current) return;
    
    setIsDragging(true);
    dragStartRef.current = {
      x: e.clientX,
      y: e.clientY,
      scrollLeft: containerRef.current.scrollLeft,
      scrollTop: containerRef.current.scrollTop,
    };
    
    e.preventDefault();
  }, []);

  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (!isDragging || !containerRef.current) return;
    
    e.preventDefault();
    
    const deltaX = e.clientX - dragStartRef.current.x;
    const deltaY = e.clientY - dragStartRef.current.y;
    
    containerRef.current.scrollLeft = dragStartRef.current.scrollLeft - deltaX;
    containerRef.current.scrollTop = dragStartRef.current.scrollTop - deltaY;
  }, [isDragging]);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  const handleMouseLeave = useCallback(() => {
    setIsDragging(false);
  }, []);

  // Zoom with mouse wheel
  const handleWheel = useCallback((e: React.WheelEvent<HTMLDivElement>) => {
    e.preventDefault();
    
    const zoomFactor = 0.1;
    const delta = e.deltaY > 0 ? -zoomFactor : zoomFactor;
    const newZoom = Math.min(Math.max(zoomLevel + delta, 0.1), 10); // Allow up to 1000% zoom for large datasets
    
    setZoomLevel(newZoom);
  }, [zoomLevel]);

  // Auto-adjust zoom level based on node count
  useEffect(() => {
    setZoomLevel(optimalZoom);
  }, [optimalZoom]);

  // Reset zoom function - back to optimal zoom
  const resetZoom = useCallback(() => {
    setZoomLevel(optimalZoom);
  }, [optimalZoom]);

  // Show loading state during hydration
  if (!isClient || !treeRoot) {
    return (
      <div className="menu-tree-chart">
        <div className="chart-header">
          <div className="chart-title-section">
            <h3>메뉴 구조 트리 차트</h3>
            <div style={{ fontSize: '0.8rem', color: '#a0aec0', marginTop: '0.25rem' }}>
              로딩 중...
            </div>
          </div>
        </div>
        <div className="chart-container" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '400px' }}>
          <div>트리 구조를 로딩하고 있습니다...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="menu-tree-chart">
      <div className="chart-header">
        <div className="chart-title-section">
          <h3>메뉴 구조 트리 차트</h3>

          <div className="zoom-controls">
            <button 
              onClick={() => setZoomLevel(Math.min(zoomLevel + 0.2, 10))}
              className="zoom-button"
              title="확대"
            >
              🔍+
            </button>
            <span className="zoom-level">{Math.round(zoomLevel * 100)}%</span>
            <button 
              onClick={() => setZoomLevel(Math.max(zoomLevel - 0.2, 0.1))}
              className="zoom-button"
              title="축소"
            >
              🔍-
            </button>
            <button 
              onClick={resetZoom}
              className="zoom-button reset-zoom"
              title="원래 크기"
            >
              ↻
            </button>
            <button 
              onClick={() => setShowLegend(!showLegend)}
              className="zoom-button"
              title="범례 표시/숨김"
              style={{ 
                backgroundColor: showLegend ? '#4299e1' : '#e2e8f0',
                color: showLegend ? 'white' : '#4a5568'
              }}
            >
              📊
            </button>
          </div>
        </div>

      </div>

      <div 
        ref={containerRef}
        className="chart-container"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseLeave}
        onWheel={handleWheel}
        style={{ cursor: isDragging ? 'grabbing' : 'grab' }}
      >
        <svg 
          ref={svgRef}
          width={dimensions.width} 
          height={dimensions.height}
          viewBox={`0 0 ${dimensions.width} ${dimensions.height}`}
          className="tree-svg"
          style={{ 
            transform: `scale(${zoomLevel})`,
            transformOrigin: 'top left',
            transition: isDragging ? 'none' : 'transform 0.2s ease'
          }}
        >
          {/* Render curved edges */}
          <g className="edges">
            {allNodes.edges.map((edge, index) => {
              const fromX = edge.from.x;
              const fromY = edge.from.y + getNodeHeight(edge.from) / 2;
              const toX = edge.to.x;
              const toY = edge.to.y - getNodeHeight(edge.to) / 2;
              
              // Create curved path
              const midY = fromY + (toY - fromY) / 2;
              const pathData = `M ${fromX} ${fromY} C ${fromX} ${midY} ${toX} ${midY} ${toX} ${toY}`;
              
              return (
                <path
                  key={index}
                  d={pathData}
                  stroke="#4a5568"
                  strokeWidth={nodeStyle.strokeWidth}
                  fill="none"
                  opacity="0.8"
                  className="tree-edge"
                />
              );
            })}
          </g>

          {/* Render rectangular nodes */}
          <g className="nodes">
            {allNodes.nodes.map((node) => {
              const nodeWidth = getNodeWidth(node);
              const nodeHeight = getNodeHeight(node);
              const nodeX = node.x - nodeWidth / 2;
              const nodeY = node.y - nodeHeight / 2;
              
              return (
                <g key={node.id}>
                  {/* Node rectangle with gradient */}
                  <defs>
                    <linearGradient id={`gradient-${node.id}`} x1="0%" y1="0%" x2="0%" y2="100%">
                      <stop offset="0%" stopColor={getNodeColor(node)} stopOpacity="1" />
                      <stop offset="100%" stopColor={getNodeColor(node)} stopOpacity="0.8" />
                    </linearGradient>
                  </defs>
                  
                  <rect
                    x={nodeX}
                    y={nodeY}
                    width={nodeWidth}
                    height={nodeHeight}
                    rx="24"
                    ry="24"
                    fill={`url(#gradient-${node.id})`}
                    stroke="#1a202c"
                    strokeWidth={nodeStyle.strokeWidth}
                    className="tree-node-rect"
                    onMouseEnter={() => setHoveredNode(node)}
                    onMouseLeave={() => setHoveredNode(null)}
                    onClick={(e) => {
                      e.stopPropagation();
                      if (!isDragging) {
                        setSelectedNode(selectedNode?.id === node.id ? null : node);
                        if (node.children.length > 0) {
                          toggleNodeExpansion(node.id);
                        }
                      }
                    }}
                    style={{ cursor: isDragging ? 'grabbing' : 'pointer' }}
                  />
                  
                  {/* Node title - center top */}
                  <text
                    x={node.x}
                    y={node.y - 15}
                    textAnchor="middle"
                    dominantBaseline="middle"
                    fill="white"
                    fontSize={nodeStyle.fontSize.title}
                    fontWeight="800"
                    pointerEvents="none"
                    className="node-title"
                    style={{ textShadow: '2px 2px 4px rgba(0,0,0,0.8)' }}
                  >
                    {node.name}
                  </text>
                  
                  {/* Node count - center */}
                  <text
                    x={node.x}
                    y={node.y + 5}
                    textAnchor="middle"
                    dominantBaseline="middle"
                    fill="white"
                    fontSize={nodeStyle.fontSize.count}
                    fontWeight="bold"
                    pointerEvents="none"
                    className="node-count"
                    style={{ textShadow: '1px 1px 2px rgba(0,0,0,0.6)' }}
                  >
                    {node.totalCount}개
                  </text>
                  
                  {/* Expand/Collapse indicator - center bottom */}
                  {node.children.length > 0 && (
                    <text
                      x={node.x}
                      y={node.y + 25}
                      textAnchor="middle"
                      dominantBaseline="middle"
                      fill={node.isExpanded ? '#68d391' : '#90cdf4'}
                      fontSize="12"
                      fontWeight="bold"
                      pointerEvents="none"
                      className="expand-indicator"
                      style={{ 
                        textShadow: '1px 1px 2px rgba(0,0,0,0.5)',
                        transition: 'fill 0.2s ease'
                      }}
                    >
                      {node.isExpanded ? '▼' : '▶'}
                    </text>
                  )}
                </g>
              );
            })}
          </g>
        </svg>

        {/* Tooltip */}
        {hoveredNode && (
          <div 
            className="chart-tooltip"
            style={{
              left: hoveredNode.x + 20,
              top: hoveredNode.y - 10
            }}
          >
            <div className="tooltip-title">{hoveredNode.name}</div>
            <div className="tooltip-info">
              <div>직접 메뉴: {hoveredNode.count}개</div>
              <div>총 메뉴: {hoveredNode.totalCount}개</div>
              <div>하위 카테고리: {hoveredNode.children.length}개</div>
              <div>레벨: {hoveredNode.level}</div>
            </div>
          </div>
        )}

        {/* Legend inside chart container */}
        {showLegend && (
          <div className="chart-legend">
            <div className="legend-header">
              <h4 className="legend-title">
                <span className="legend-icon">📊</span>
                레벨별 색상 범례
              </h4>
              <div className="legend-subtitle">
                노드의 계층 구조를 색상으로 구분합니다
              </div>
            </div>
            
            <div className="legend-items">
              {legendData.map((item) => (
                <div key={item.level} className="legend-item">
                  <div 
                    className="legend-color-box"
                    style={{ backgroundColor: item.color }}
                  />
                  <div className="legend-item-content">
                    <div className="legend-item-label">
                      Level {item.level}: {item.label}
                    </div>
                    <div className="legend-item-description">
                      {item.description}
                    </div>
                  </div>
                </div>
              ))}
            </div>
            
            {/* Current tree stats */}
            <div className="legend-stats">
              <div className="legend-stats-title">트리 통계</div>
              <div className="legend-stats-content">
                <div className="legend-stat-item">
                  <span className="legend-stat-label">표시 중:</span>
                  <span className="legend-stat-value">{allNodes.nodes.length}개 노드</span>
                </div>
                <div className="legend-stat-item">
                  <span className="legend-stat-label">전체:</span>
                  <span className="legend-stat-value">{(() => {
                    if (!treeRoot) return 0;
                    const countAllNodes = (node: TreeNode): number => {
                      return 1 + node.children.reduce((sum, child) => sum + countAllNodes(child), 0);
                    };
                    return countAllNodes(treeRoot);
                  })()}개 노드</span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Selected node details */}
      {selectedNode && (
        <div className="chart-details">
          <div className="details-card">
            <h4>{selectedNode.name}</h4>
            <div className="details-stats">
              <div className="stat">
                <span className="stat-label">직접 메뉴</span>
                <span className="stat-value">{selectedNode.count}</span>
              </div>
              <div className="stat">
                <span className="stat-label">총 메뉴</span>
                <span className="stat-value">{selectedNode.totalCount}</span>
              </div>
              <div className="stat">
                <span className="stat-label">하위 카테고리</span>
                <span className="stat-value">{selectedNode.children.length}</span>
              </div>
              <div className="stat">
                <span className="stat-label">레벨</span>
                <span className="stat-value">{selectedNode.level}</span>
              </div>
            </div>
            
            {selectedNode.menuLinks.length > 0 && (
              <div className="details-menus">
                <h5>이 노드와 관련된 메뉴 링크 ({selectedNode.menuLinks.length}개)</h5>
                <div className="menu-categories">
                  {(() => {
                    // Separate direct and descendant menu links
                    const nodePath = (() => {
                      // Reconstruct the node's path from its position in the tree
                      // This is a bit tricky since we need to find the node's full path
                      const findNodePath = (node: TreeNode, targetId: string, currentPath: string = ''): string | null => {
                        if (node.id === targetId) {
                          return currentPath;
                        }
                        for (const child of node.children) {
                          const childPath = currentPath ? `${currentPath}^${child.name}` : child.name;
                          const result = findNodePath(child, targetId, childPath);
                          if (result !== null) {
                            return result;
                          }
                        }
                        return null;
                      };
                      
                      if (!treeRoot) return '';
                      if (selectedNode.level === 1) return ''; // Root node
                      return findNodePath(treeRoot, selectedNode.id) || '';
                    })();
                    
                    const directMenus = selectedNode.menuLinks.filter(menu => menu.menu_path === nodePath);
                    const descendantMenus = selectedNode.menuLinks.filter(menu => menu.menu_path !== nodePath);
                    
                    return (
                      <>
                        {directMenus.length > 0 && (
                          <div className="menu-category">
                            <h6 className="category-title">직접 메뉴 ({directMenus.length}개)</h6>
                            <div className="menu-list">
                              {directMenus.map((menu) => (
                                <div key={menu.id} className="menu-item direct-menu">
                                  <div className="menu-item-header">
                                    <span className="menu-id">#{menu.id}</span>
                                    <span className="menu-type-badge direct">직접</span>
                                    {menu.document_id && (
                                      <span className="menu-doc-id">Doc: {menu.document_id}</span>
                                    )}
                                  </div>
                                  <div className="menu-path">{menu.menu_path}</div>
                                  {menu.pc_url && (
                                    <div className="menu-url">
                                      <span className="url-label">PC:</span> 
                                      <a href={menu.pc_url} target="_blank" rel="noopener noreferrer" className="url-link">
                                        {menu.pc_url}
                                      </a>
                                    </div>
                                  )}
                                  {menu.mobile_url && (
                                    <div className="menu-url">
                                      <span className="url-label">Mobile:</span>
                                      <a href={menu.mobile_url} target="_blank" rel="noopener noreferrer" className="url-link">
                                        {menu.mobile_url}
                                      </a>
                                    </div>
                                  )}
                                  {menu.created_at && (
                                    <div className="menu-meta">
                                      생성: {new Date(menu.created_at).toLocaleString('ko-KR', {
                                        year: 'numeric',
                                        month: '2-digit',
                                        day: '2-digit',
                                        hour: '2-digit',
                                        minute: '2-digit'
                                      })}
                                      {menu.created_by && ` by ${menu.created_by}`}
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                        
                        {descendantMenus.length > 0 && (
                          <div className="menu-category">
                            <h6 className="category-title">하위 메뉴 ({descendantMenus.length}개)</h6>
                            <div className="menu-list">
                              {descendantMenus.map((menu) => (
                                <div key={menu.id} className="menu-item descendant-menu">
                                  <div className="menu-item-header">
                                    <span className="menu-id">#{menu.id}</span>
                                    <span className="menu-type-badge descendant">하위</span>
                                    {menu.document_id && (
                                      <span className="menu-doc-id">Doc: {menu.document_id}</span>
                                    )}
                                  </div>
                                  <div className="menu-path">{menu.menu_path}</div>
                                  {menu.pc_url && (
                                    <div className="menu-url">
                                      <span className="url-label">PC:</span> 
                                      <a href={menu.pc_url} target="_blank" rel="noopener noreferrer" className="url-link">
                                        {menu.pc_url}
                                      </a>
                                    </div>
                                  )}
                                  {menu.mobile_url && (
                                    <div className="menu-url">
                                      <span className="url-label">Mobile:</span>
                                      <a href={menu.mobile_url} target="_blank" rel="noopener noreferrer" className="url-link">
                                        {menu.mobile_url}
                                      </a>
                                    </div>
                                  )}
                                  {menu.created_at && (
                                    <div className="menu-meta">
                                      생성: {new Date(menu.created_at).toLocaleString('ko-KR', {
                                        year: 'numeric',
                                        month: '2-digit',
                                        day: '2-digit',
                                        hour: '2-digit',
                                        minute: '2-digit'
                                      })}
                                      {menu.created_by && ` by ${menu.created_by}`}
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </>
                    );
                  })()}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
