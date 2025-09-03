'use client';

import React, { useState, useMemo } from 'react';
import { MenuLink } from '../types';

interface TreeNode {
  name: string;
  path: string;
  children: TreeNode[];
  count: number;
  totalCount: number;
  level: number;
  menuLinks: MenuLink[];
}

interface MenuTreeViewProps {
  menuLinks: MenuLink[];
  onSelectNode?: (node: TreeNode) => void;
}

interface TreeNodeComponentProps {
  node: TreeNode;
  isExpanded: boolean;
  onToggle: () => void;
  onSelect: (node: TreeNode) => void;
  selectedPath?: string;
}

function TreeNodeComponent({ 
  node, 
  isExpanded, 
  onToggle, 
  onSelect, 
  selectedPath 
}: TreeNodeComponentProps) {
  const hasChildren = node.children.length > 0;
  const isSelected = selectedPath === node.path;
  
  return (
    <div className="tree-node">
      <div 
        className={`tree-node-header ${isSelected ? 'selected' : ''}`}
        onClick={() => onSelect(node)}
        style={{ paddingLeft: `${node.level * 1.5}rem` }}
      >
        <div className="tree-node-content">
          {hasChildren && (
            <button 
              className={`tree-toggle ${isExpanded ? 'expanded' : ''}`}
              onClick={(e) => {
                e.stopPropagation();
                onToggle();
              }}
            >
              <svg width="12" height="12" viewBox="0 0 12 12">
                <path 
                  d="M4 2 L8 6 L4 10" 
                  stroke="currentColor" 
                  strokeWidth="2" 
                  fill="none"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
          )}
          
          <div className="tree-node-icon">
            {hasChildren ? (
              <svg width="16" height="16" viewBox="0 0 16 16">
                <path 
                  d="M1.75 2.5h12.5a.75.75 0 0 1 .75.75v9.5a.75.75 0 0 1-.75.75H1.75a.75.75 0 0 1-.75-.75v-9.5a.75.75 0 0 1 .75-.75Z" 
                  fill="currentColor"
                  opacity="0.3"
                />
                <path 
                  d="M1.75 2.5h12.5a.75.75 0 0 1 .75.75v2H1v-2a.75.75 0 0 1 .75-.75Z" 
                  fill="currentColor"
                />
              </svg>
            ) : (
              <svg width="16" height="16" viewBox="0 0 16 16">
                <path 
                  d="M2 2.5A1.5 1.5 0 0 1 3.5 1h5.086a1.5 1.5 0 0 1 1.06.44l2.914 2.914a1.5 1.5 0 0 1 .44 1.06V13.5A1.5 1.5 0 0 1 11.5 15h-8A1.5 1.5 0 0 1 2 13.5V2.5Z" 
                  fill="currentColor"
                  opacity="0.6"
                />
              </svg>
            )}
          </div>
          
          <span className="tree-node-name">{node.name}</span>
          
          <div className="tree-node-badges">
            <span className="tree-node-count direct">{node.count}</span>
            {node.totalCount > node.count && (
              <span className="tree-node-count total">+{node.totalCount - node.count}</span>
            )}
          </div>
        </div>
      </div>
      
      {hasChildren && isExpanded && (
        <div className="tree-node-children">
          {node.children.map((child) => (
            <TreeNodeComponentWrapper 
              key={child.path} 
              node={child} 
              onSelect={onSelect}
              selectedPath={selectedPath}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function TreeNodeComponentWrapper({ 
  node, 
  onSelect, 
  selectedPath 
}: { 
  node: TreeNode; 
  onSelect: (node: TreeNode) => void;
  selectedPath?: string;
}) {
  const [isExpanded, setIsExpanded] = useState(false);
  
  return (
    <TreeNodeComponent
      node={node}
      isExpanded={isExpanded}
      onToggle={() => setIsExpanded(!isExpanded)}
      onSelect={onSelect}
      selectedPath={selectedPath}
    />
  );
}

export default function MenuTreeView({ menuLinks, onSelectNode }: MenuTreeViewProps) {
  const [selectedPath, setSelectedPath] = useState<string>();
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(new Set());

  const treeData = useMemo(() => {
    const root: TreeNode = {
      name: 'Root',
      path: '',
      children: [],
      count: 0,
      totalCount: 0,
      level: -1,
      menuLinks: []
    };

    // Build tree structure
    menuLinks.forEach(menuLink => {
      const pathParts = menuLink.menu_path.split('^');
      let currentNode = root;
      let currentPath = '';

      pathParts.forEach((part, index) => {
        currentPath = index === 0 ? part : `${currentPath}^${part}`;
        
        let childNode = currentNode.children.find(child => child.name === part);
        if (!childNode) {
          childNode = {
            name: part,
            path: currentPath,
            children: [],
            count: 0,
            totalCount: 0,
            level: index,
            menuLinks: []
          };
          currentNode.children.push(childNode);
        }
        
        // If this is the final part, add the menu link
        if (index === pathParts.length - 1) {
          childNode.count++;
          childNode.menuLinks.push(menuLink);
        }
        
        currentNode = childNode;
      });
    });

    // Calculate total counts (including children)
    function calculateTotalCounts(node: TreeNode): number {
      let total = node.count;
      node.children.forEach(child => {
        total += calculateTotalCounts(child);
      });
      node.totalCount = total;
      return total;
    }

    root.children.forEach(calculateTotalCounts);

    // Sort children by total count (descending)
    function sortChildren(node: TreeNode) {
      node.children.sort((a, b) => b.totalCount - a.totalCount);
      node.children.forEach(sortChildren);
    }
    
    sortChildren(root);

    return root.children;
  }, [menuLinks]);

  const handleSelectNode = (node: TreeNode) => {
    setSelectedPath(node.path);
    onSelectNode?.(node);
  };

  const expandAll = () => {
    const allPaths = new Set<string>();
    function collectPaths(nodes: TreeNode[]) {
      nodes.forEach(node => {
        if (node.children.length > 0) {
          allPaths.add(node.path);
          collectPaths(node.children);
        }
      });
    }
    collectPaths(treeData);
    setExpandedPaths(allPaths);
  };

  const collapseAll = () => {
    setExpandedPaths(new Set());
  };

  const totalMenus = menuLinks.length;
  const totalCategories = treeData.length;

  return (
    <div className="menu-tree-view">
      <div className="tree-header">
        <div className="tree-title">
          <h3>메뉴 구조 트리</h3>
          <div className="tree-stats">
            <span className="stat-item">
              <span className="stat-label">카테고리</span>
              <span className="stat-value">{totalCategories}</span>
            </span>
            <span className="stat-item">
              <span className="stat-label">총 메뉴</span>
              <span className="stat-value">{totalMenus}</span>
            </span>
          </div>
        </div>
        
        <div className="tree-actions">
          <button className="tree-action-btn" onClick={expandAll}>
            모두 펼치기
          </button>
          <button className="tree-action-btn" onClick={collapseAll}>
            모두 접기
          </button>
        </div>
      </div>

      <div className="tree-legend">
        <div className="legend-item">
          <span className="legend-badge direct">5</span>
          <span className="legend-text">직접 메뉴 수</span>
        </div>
        <div className="legend-item">
          <span className="legend-badge total">+10</span>
          <span className="legend-text">하위 메뉴 수</span>
        </div>
      </div>

      <div className="tree-container">
        {treeData.map((node) => (
          <TreeNodeComponentWrapper 
            key={node.path} 
            node={node} 
            onSelect={handleSelectNode}
            selectedPath={selectedPath}
          />
        ))}
      </div>
    </div>
  );
}
