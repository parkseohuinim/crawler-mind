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
  isExpanded: boolean;
  isVisible: boolean;
}

interface MenuTreeChartProps {
  menuLinks: MenuLink[];
}

export default function MenuTreeChart({ menuLinks }: MenuTreeChartProps) {
  const [selectedNode, setSelectedNode] = useState<TreeNode | null>(null);
  const [hoveredNode, setHoveredNode] = useState<TreeNode | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [zoomLevel, setZoomLevel] = useState(() => {
    return 1.5;
  });
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const dragStartRef = useRef({ x: 0, y: 0, scrollLeft: 0, scrollTop: 0 });
  const [scrollPosition, setScrollPosition] = useState({ left: 0, top: 0 });

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
    nodeMap.set('', rootNode);

    menuLinks.forEach(menuLink => {
      const pathParts = menuLink.menu_path.split('^').filter(part => part.trim() !== '');
      let currentPath = '';
      let parentNode = rootNode;

      pathParts.forEach((part, index) => {
        const previousPath = currentPath;
        currentPath = currentPath ? `${currentPath}^${part}` : part;
        const level = index + 2;

        if (!nodeMap.has(currentPath)) {
          const newNode: TreeNode = {
            id: `node-${++nodeCounter}`,
            name: part,
            children: [],
            count: 0,
            totalCount: 0,
            level,
            x: 0,
            y: 0,
            menuLinks: [],
            isExpanded: false,
            isVisible: level <= 2
          };

          nodeMap.set(currentPath, newNode);
          parentNode.children.push(newNode);
        }

        const currentNode = nodeMap.get(currentPath)!;
        
        if (index === pathParts.length - 1) {
          currentNode.menuLinks.push(menuLink);
          currentNode.count++;
        }

        parentNode = currentNode;
      });
    });

    menuLinks.forEach(menuLink => {
      const menuPath = menuLink.menu_path;
      
      nodeMap.forEach((node, nodePath) => {
        if (nodePath === '') return;
        
        if (menuPath === nodePath || menuPath.startsWith(nodePath + '^')) {
          const alreadyExists = node.menuLinks.some(existing => existing.id === menuLink.id);
          if (!alreadyExists) {
            node.menuLinks.push(menuLink);
          }
        }
      });
    });

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

  const [treeRoot, setTreeRoot] = useState<TreeNode | null>(null);
  const [showLegend, setShowLegend] = useState<boolean>(true);
  const [isClient, setIsClient] = useState(false);

  useEffect(() => {
    setIsClient(true);
    setTreeRoot(generateCollapsibleTree(menuLinks));
  }, [menuLinks]);
  
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
  
  const optimalZoom = 1.0;

  const legendData = [
    { level: 1, color: '#667eea', label: '루트', description: '최상위 노드' },
    { level: 2, color: '#764ba2', label: '메인 카테고리', description: '주요 메뉴 분류' },
    { level: 3, color: '#f093fb', label: '서브 카테고리', description: '하위 메뉴 분류' },
    { level: 4, color: '#4facfe', label: '세부 카테고리', description: '상세 메뉴 분류' },
    { level: 5, color: '#43e97b', label: '아이템', description: '개별 메뉴 항목' },
  ];

  const toggleNodeExpansion = useCallback((nodeId: string) => {
    const updateNodeRecursively = (node: TreeNode, parentNode?: TreeNode): TreeNode => {
      if (node.id === nodeId) {
        const newExpanded = !node.isExpanded;
        
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
      
      const hasTargetChild = node.children.some(child => child.id === nodeId);
      if (hasTargetChild) {
        return {
          ...node,
          children: node.children.map(child => {
            if (child.id === nodeId) {
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
              const collapseDescendants = (node: TreeNode): TreeNode => ({
                ...node,
                isExpanded: false,
                isVisible: node.level <= 2,
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

  const calculateNodePositions = useCallback((root: TreeNode, canvasWidth: number = 1200, canvasHeight: number = 800) => {
    const visibleNodes: TreeNode[] = [];
    const edges: { from: TreeNode; to: TreeNode }[] = [];
    
    const rootX = canvasWidth / 2;
    const rootY = 100;
    
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
            const startX = x - ((childrenCount - 1) * nodeStyle.horizontalSpacing) / 2;
            
            let childIndex = 0;
            visibleChildren.forEach(child => {
              const childX = startX + (childIndex * nodeStyle.horizontalSpacing);
              const childY = y + nodeStyle.verticalSpacing;
              traverse(child, childX, childY, updatedNode);
              childIndex++;
            });
          } else {
            const itemsPerRow = 4;
            const totalRows = Math.ceil(childrenCount / itemsPerRow);
            const rowHeight = nodeStyle.verticalSpacing;
            const itemSpacing = nodeStyle.horizontalSpacing;
            
            const firstRowStartX = x - ((Math.min(itemsPerRow, childrenCount) - 1) * itemSpacing) / 2;
            
            let childIndex = 0;
            visibleChildren.forEach(child => {
              const row = Math.floor(childIndex / itemsPerRow);
              const col = childIndex % itemsPerRow;
              
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
    
    traverse(root, rootX, rootY);
    
    return { nodes: visibleNodes, edges };
  }, [nodeStyle]);

  const baseDimensions = useMemo(() => ({
    width: 1200,
    height: 800
  }), []);

  const allNodes = useMemo(() => {
    if (!treeRoot) return { nodes: [], edges: [] };
    return calculateNodePositions(treeRoot, baseDimensions.width, baseDimensions.height);
  }, [treeRoot, calculateNodePositions, baseDimensions]);

  const getNodeColor = (node: TreeNode) => {
    if (selectedNode?.id === node.id) return '#667eea';
    if (hoveredNode?.id === node.id) return '#8b5cf6';
    
    const legendItem = legendData.find(item => item.level === node.level);
    let baseColor = legendItem?.color || '#94a3b8';
    
    return baseColor;
  };

  const getNodeWidth = (node: TreeNode) => {
    return nodeStyle.width;
  };

  const getNodeHeight = (node: TreeNode) => {
    return nodeStyle.height;
  };

  const dimensions = useMemo(() => {
    if (allNodes.nodes.length === 0) return baseDimensions;
    
    const maxWidth = Math.max(...allNodes.nodes.map(node => node.x)) + nodeStyle.width + 100;
    const maxHeight = Math.max(...allNodes.nodes.map(node => node.y)) + nodeStyle.height + 100;
    
    return {
      width: Math.max(baseDimensions.width, maxWidth),
      height: Math.max(baseDimensions.height, maxHeight)
    };
  }, [allNodes.nodes, nodeStyle, baseDimensions]);

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

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const handleWheel = (e: WheelEvent) => {
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault();
        
        const zoomFactor = 0.1;
        const delta = e.deltaY > 0 ? -zoomFactor : zoomFactor;
        const newZoom = Math.min(Math.max(zoomLevel + delta, 0.1), 10);
        
        setZoomLevel(newZoom);
      }
    };

    container.addEventListener('wheel', handleWheel, { passive: false });
    const handleScroll = () => {
      setScrollPosition({ left: container.scrollLeft, top: container.scrollTop });
    };
    container.addEventListener('scroll', handleScroll, { passive: true });
    // Initialize scroll position once mounted
    handleScroll();
    
    return () => {
      container.removeEventListener('wheel', handleWheel);
      container.removeEventListener('scroll', handleScroll);
    };
  }, [zoomLevel]);

  useEffect(() => {
    setZoomLevel(optimalZoom);
  }, [optimalZoom]);

  const resetZoom = useCallback(() => {
    setZoomLevel(optimalZoom);
  }, [optimalZoom]);
  
  // Loading state
  if (!isClient || !treeRoot) {
    return (
      <div className="modern-tree-chart">
        <div className="modern-chart-header">
          <div className="modern-chart-title-section">
            <div className="modern-chart-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M22 12h-4l-3 9L9 3l-3 9H2"></path>
              </svg>
            </div>
            <div className="modern-chart-text">
              <h3 className="modern-chart-title">메뉴 구조 트리 차트</h3>
              <div className="modern-chart-subtitle">
                로딩 중...
              </div>
            </div>
          </div>
        </div>
        <div className="modern-loading-container">
          <div className="modern-loading-content">
            <div className="modern-spinner-large"></div>
            <div className="modern-loading-text">트리 구조를 로딩하고 있습니다...</div>
            <div className="modern-loading-subtext">잠시만 기다려주세요</div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="modern-tree-chart">
      <div className="modern-chart-header">
        <div className="modern-chart-title-section">
          <div className="modern-chart-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M22 12h-4l-3 9L9 3l-3 9H2"></path>
            </svg>
          </div>
          <div className="modern-chart-text">
            <h3 className="modern-chart-title">메뉴 구조 트리 차트</h3>
            <div className="modern-chart-subtitle">
              Ctrl/Cmd + 마우스 휠로 확대/축소 가능
            </div>
          </div>
        </div>

        <div className="modern-zoom-controls">
          <button 
            onClick={() => setZoomLevel(Math.min(zoomLevel + 0.2, 10))}
            className="modern-zoom-button"
            title="확대"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8"></circle>
              <path d="m21 21-4.35-4.35"></path>
              <line x1="11" y1="8" x2="11" y2="14"></line>
              <line x1="8" y1="11" x2="14" y2="11"></line>
            </svg>
          </button>
          <span className="modern-zoom-level">{Math.round(zoomLevel * 100)}%</span>
          <button 
            onClick={() => setZoomLevel(Math.max(zoomLevel - 0.2, 0.1))}
            className="modern-zoom-button"
            title="축소"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8"></circle>
              <path d="m21 21-4.35-4.35"></path>
              <line x1="8" y1="11" x2="14" y2="11"></line>
            </svg>
          </button>
          <button 
            onClick={resetZoom}
            className="modern-zoom-button modern-reset-zoom"
            title="원래 크기"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"></path>
              <path d="M21 3v5h-5"></path>
              <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"></path>
              <path d="M3 21v-5h5"></path>
            </svg>
          </button>
          <button 
            onClick={() => setShowLegend(!showLegend)}
            className={`modern-zoom-button modern-legend-toggle ${showLegend ? 'active' : ''}`}
            title="범례 표시/숨김"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 3v18h18"></path>
              <path d="M18.7 8a3 3 0 0 0-2.7-2 3 3 0 0 0-2.7 2"></path>
              <path d="M9 9h9v9H9"></path>
            </svg>
          </button>
        </div>
      </div>

      <div className="modern-chart-main-layout">
        <div className="modern-chart-left-panel">
          <div 
            ref={containerRef}
            className="modern-chart-container"
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseLeave}
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
                      <defs>
                        <linearGradient id={`gradient-${node.id}`} x1="0%" y1="0%" x2="100%" y2="100%">
                          <stop offset="0%" stopColor={getNodeColor(node)} stopOpacity="1" />
                          <stop offset="50%" stopColor={getNodeColor(node)} stopOpacity="0.9" />
                          <stop offset="100%" stopColor={getNodeColor(node)} stopOpacity="0.7" />
                        </linearGradient>
                        <filter id={`glow-${node.id}`}>
                          <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
                          <feMerge> 
                            <feMergeNode in="coloredBlur"/>
                            <feMergeNode in="SourceGraphic"/>
                          </feMerge>
                        </filter>
                      </defs>
                      
                      <rect
                        x={nodeX}
                        y={nodeY}
                        width={nodeWidth}
                        height={nodeHeight}
                        rx="24"
                        ry="24"
                        fill={`url(#gradient-${node.id})`}
                        stroke="rgba(255, 255, 255, 0.3)"
                        strokeWidth={nodeStyle.strokeWidth}
                        className="tree-node-rect"
                        filter={`url(#glow-${node.id})`}
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
                      
                      {node.children.length > 0 && (
                        <text
                          x={node.x}
                          y={node.y + 25}
                          textAnchor="middle"
                          dominantBaseline="middle"
                          fill={node.isExpanded ? '#43e97b' : '#667eea'}
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

            {hoveredNode && (
              <div 
                className="chart-tooltip"
                style={(() => {
                  const container = containerRef.current;
                  const svg = svgRef.current;
                  if (!container || !svg) {
                    return {
                      left: hoveredNode.x * zoomLevel,
                      top: ((hoveredNode.y - (nodeStyle.height / 2)) * zoomLevel) - 4,
                      transform: 'translate(-50%, -100%)'
                    } as React.CSSProperties;
                  }
                  const containerRect = container.getBoundingClientRect();
                  const svgRect = svg.getBoundingClientRect();
                  const offsetXWithinContainer = svgRect.left - containerRect.left;
                  const offsetYWithinContainer = svgRect.top - containerRect.top;
                  const left = scrollPosition.left + offsetXWithinContainer + (hoveredNode.x * zoomLevel);
                  const top = scrollPosition.top + offsetYWithinContainer + ((hoveredNode.y - (nodeStyle.height / 2)) * zoomLevel) - 4;
                  return {
                    left,
                    top,
                    transform: 'translate(-50%, -100%)'
                  } as React.CSSProperties;
                })()}
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

            {showLegend && (
              <div className="modern-chart-legend">
                <div className="modern-legend-header">
                  <div className="modern-legend-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M3 3v18h18"></path>
                      <path d="M18.7 8a3 3 0 0 0-2.7-2 3 3 0 0 0-2.7 2"></path>
                      <path d="M9 9h9v9H9"></path>
                    </svg>
                  </div>
                  <div className="modern-legend-text">
                    <h4 className="modern-legend-title">레벨별 색상 범례</h4>
                    <div className="modern-legend-subtitle">
                      노드의 계층 구조를 색상으로 구분합니다
                    </div>
                  </div>
                </div>
                
                <div className="modern-legend-items">
                  {legendData.map((item) => (
                    <div key={item.level} className="modern-legend-item">
                      <div 
                        className="modern-legend-color-box"
                        style={{ backgroundColor: item.color }}
                      />
                      <div className="modern-legend-item-content">
                        <div className="modern-legend-item-label">
                          Level {item.level}: {item.label}
                        </div>
                        <div className="modern-legend-item-description">
                          {item.description}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
                
                <div className="modern-legend-stats">
                  <div className="modern-legend-stats-title">트리 통계</div>
                  <div className="modern-legend-stats-content">
                    <div className="modern-legend-stat-item">
                      <span className="modern-legend-stat-label">표시 중:</span>
                      <span className="modern-legend-stat-value">{allNodes.nodes.length}개 노드</span>
                    </div>
                    <div className="modern-legend-stat-item">
                      <span className="modern-legend-stat-label">전체:</span>
                      <span className="modern-legend-stat-value">{(() => {
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
        </div>

        <div className="modern-chart-right-panel">
          {selectedNode ? (
            <div className="modern-chart-details">
              <div className="modern-details-card">
                <div className="modern-details-header">
                  <div className="modern-details-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <circle cx="12" cy="12" r="3"></circle>
                      <path d="M12 1v6m0 6v6m11-7h-6m-6 0H1"></path>
                    </svg>
                  </div>
                  <h4 className="modern-details-title">{selectedNode.name}</h4>
                </div>
                <div className="modern-details-stats">
                  <div className="modern-stat">
                    <span className="modern-stat-label">직접 메뉴</span>
                    <span className="modern-stat-value">{selectedNode.count}</span>
                  </div>
                  <div className="modern-stat">
                    <span className="modern-stat-label">총 메뉴</span>
                    <span className="modern-stat-value">{selectedNode.totalCount}</span>
                  </div>
                  <div className="modern-stat">
                    <span className="modern-stat-label">하위 카테고리</span>
                    <span className="modern-stat-value">{selectedNode.children.length}</span>
                  </div>
                  <div className="modern-stat">
                    <span className="modern-stat-label">레벨</span>
                    <span className="modern-stat-value">{selectedNode.level}</span>
                  </div>
                </div>
                
                {selectedNode.menuLinks.length > 0 && (
                  <div className="modern-details-menus">
                    <div className="modern-details-menus-header">
                      <div className="modern-details-menus-icon">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                          <polyline points="14,2 14,8 20,8"></polyline>
                          <line x1="16" y1="13" x2="8" y2="13"></line>
                          <line x1="16" y1="17" x2="8" y2="17"></line>
                          <polyline points="10,9 9,9 8,9"></polyline>
                        </svg>
                      </div>
                      <h5 className="modern-details-menus-title">이 노드와 관련된 메뉴 링크 ({selectedNode.menuLinks.length}개)</h5>
                    </div>
                    <div className="modern-menu-categories">
                      {(() => {
                        const nodePath = (() => {
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
                          if (selectedNode.level === 1) return '';
                          return findNodePath(treeRoot, selectedNode.id) || '';
                        })();
                        
                        const directMenus = selectedNode.menuLinks.filter(menu => menu.menu_path === nodePath);
                        const descendantMenus = selectedNode.menuLinks.filter(menu => menu.menu_path !== nodePath);
                        
                        return (
                          <>
                            {directMenus.length > 0 && (
                              <div className="modern-menu-category">
                                <h6 className="modern-category-title">직접 메뉴 ({directMenus.length}개)</h6>
                                <div className="modern-menu-list">
                                  {directMenus.map((menu) => (
                                    <div key={menu.id} className="modern-menu-item modern-direct-menu">
                                      <div className="modern-menu-item-header">
                                        <span className="modern-menu-id">#{menu.id}</span>
                                        <span className="modern-menu-type-badge modern-direct">직접</span>
                                        {menu.document_id && (
                                          <span className="modern-menu-doc-id">Doc: {menu.document_id}</span>
                                        )}
                                      </div>
                                      <div className="modern-menu-path">{menu.menu_path}</div>
                                      {menu.pc_url && (
                                        <div className="modern-menu-url">
                                          <span className="modern-url-label">PC:</span> 
                                          <a href={menu.pc_url} target="_blank" rel="noopener noreferrer" className="modern-url-link">
                                            {menu.pc_url}
                                          </a>
                                        </div>
                                      )}
                                      {menu.mobile_url && (
                                        <div className="modern-menu-url">
                                          <span className="modern-url-label">Mobile:</span>
                                          <a href={menu.mobile_url} target="_blank" rel="noopener noreferrer" className="modern-url-link">
                                            {menu.mobile_url}
                                          </a>
                                        </div>
                                      )}
                                      {menu.created_at && (
                                        <div className="modern-menu-meta">
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
                              <div className="modern-menu-category">
                                <h6 className="modern-category-title">하위 메뉴 ({descendantMenus.length}개)</h6>
                                <div className="modern-menu-list">
                                  {descendantMenus.map((menu) => (
                                    <div key={menu.id} className="modern-menu-item modern-descendant-menu">
                                      <div className="modern-menu-item-header">
                                        <span className="modern-menu-id">#{menu.id}</span>
                                        <span className="modern-menu-type-badge modern-descendant">하위</span>
                                        {menu.document_id && (
                                          <span className="modern-menu-doc-id">Doc: {menu.document_id}</span>
                                        )}
                                      </div>
                                      <div className="modern-menu-path">{menu.menu_path}</div>
                                      {menu.pc_url && (
                                        <div className="modern-menu-url">
                                          <span className="modern-url-label">PC:</span> 
                                          <a href={menu.pc_url} target="_blank" rel="noopener noreferrer" className="modern-url-link">
                                            {menu.pc_url}
                                          </a>
                                        </div>
                                      )}
                                      {menu.mobile_url && (
                                        <div className="modern-menu-url">
                                          <span className="modern-url-label">Mobile:</span>
                                          <a href={menu.mobile_url} target="_blank" rel="noopener noreferrer" className="modern-url-link">
                                            {menu.mobile_url}
                                          </a>
                                        </div>
                                      )}
                                      {menu.created_at && (
                                        <div className="modern-menu-meta">
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
          ) : (
            <div className="modern-no-selection-message">
              <div className="modern-no-selection-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10"></circle>
                  <path d="M8 14s1.5 2 4 2 4-2 4-2"></path>
                  <line x1="9" y1="9" x2="9.01" y2="9"></line>
                  <line x1="15" y1="9" x2="15.01" y2="9"></line>
                </svg>
              </div>
              <h3 className="modern-no-selection-title">노드를 선택하세요</h3>
              <p className="modern-no-selection-text">트리 차트에서 노드를 클릭하면<br />상세 정보가 여기에 표시됩니다.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}