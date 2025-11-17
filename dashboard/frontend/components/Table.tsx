"use client";

import { XIcon } from "lucide-react";
import type React from "react";
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";

export interface Item {
  id: string | number;
  type: string;
  data?: any;
  children?: Item[];
  __depth?: number;
}

export interface TableColumn {
  title: string;
  width?: string;
  sticky?: boolean;
  render: (item: Item, index: number) => React.ReactNode;
}

export interface TableProps {
  columns: TableColumn[];
  data: Item[];
  getRowKey?: (item: Item, index: number) => string | number;
  getRowClassName?: (item: Item, index: number) => string;
  className?: string;
  showCaret?: boolean;
  groupsRevealed?: boolean;
  onRowClick?: (item: Item) => void;
  hideSearch?: boolean;
  onSelectionChange?: (selectedKeys: Set<string | number>) => void;
  isRowSelectable?: (item: Item) => boolean;
  cellPadding?: string;
  bulkActionsBar?: React.ReactNode;
}

export default function Table({
  columns,
  data,
  getRowKey,
  getRowClassName,
  className,
  showCaret = false,
  groupsRevealed = true,
  onRowClick,
  hideSearch = true,
  onSelectionChange,
  isRowSelectable,
  cellPadding = "px-3 py-3",
  bulkActionsBar,
}: TableProps) {
  // Expand / Collapse State
  const [expandedKeys, setExpandedKeys] = useState<Set<string | number>>(() => {
    const initialKeys = new Set<string | number>();
    if (groupsRevealed) {
      const collectGroupIds = (items: Item[]) => {
        for (const it of items) {
          if (it.type === "group") {
            initialKeys.add(it.id);
          }
          if (it.children) collectGroupIds(it.children);
        }
      };
      collectGroupIds(data);
    }
    return initialKeys;
  });

  const toggleExpand = (itemId: string | number) => {
    setExpandedKeys((prev) => {
      const next = new Set(prev);
      if (next.has(itemId)) next.delete(itemId);
      else next.add(itemId);
      return next;
    });
  };

  const isExpanded = (itemId: string | number) => expandedKeys.has(itemId);

  // Selected Rows (excluding detail rows)
  const [selectedKeys, setSelectedKeys] = useState<Set<string | number>>(() => new Set());
  const isDetailRow = (item: Item) => item.type.endsWith("-detail");

  const toggleSelectRow = (item: Item) => {
    if (isDetailRow(item)) return;

    // Check if row is selectable before toggling
    if (isRowSelectable && !isRowSelectable(item)) {
      return; // Don't toggle if row is not selectable
    }
    setSelectedKeys((prev) => {
      const next = new Set(prev);
      const itemIdString = String(item.id);
      if (next.has(itemIdString)) {
        next.delete(itemIdString);
        if (item.children) unselectChildren(item.children, next);
      } else {
        next.add(itemIdString);
        if (item.children) selectChildren(item.children, next);
      }
      // Call external callback if provided
      if (onSelectionChange) {
        onSelectionChange(next);
      }
      return next;
    });
  };

  const selectChildren = (items: Item[], setToUpdate: Set<string | number>) => {
    for (const child of items) {
      setToUpdate.add(String(child.id));
      if (child.children) selectChildren(child.children, setToUpdate);
    }
  };

  const unselectChildren = (items: Item[], setToUpdate: Set<string | number>) => {
    for (const child of items) {
      setToUpdate.delete(String(child.id));
      if (child.children) unselectChildren(child.children, setToUpdate);
    }
  };

  const deselectAll = () => {
    const emptySelection = new Set<string | number>();
    setSelectedKeys(emptySelection);
    if (onSelectionChange) {
      onSelectionChange(emptySelection);
    }
  };

  // Search state
  const [isSearchFocused, setIsSearchFocused] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");

  // Combine filtering: search
  const filteredData = useMemo(() => {
    let filtered = data;
    if (searchTerm) {
      filtered = filtered.filter((item) => {
        const nameOrEmail = item.data?.name || item.data?.email || item.data?.key || "";
        return nameOrEmail.toLowerCase().includes(searchTerm.toLowerCase());
      });
    }
    return filtered;
  }, [data, searchTerm]);

  // Flatten data for rendering in <tbody>
  const flattenedData = useMemo(() => {
    const result: Item[] = [];
    const dfs = (items: Item[], depth = 0) => {
      for (const it of items) {
        it.__depth = depth;
        result.push(it);
        if (it.children && isExpanded(it.id)) {
          dfs(it.children, depth + 1);
        }
      }
    };
    dfs(filteredData);
    return result;
  }, [filteredData, expandedKeys]);

  // Select/Deselect All logic (must be after flattenedData)
  const selectableItems = useMemo(() => {
    return flattenedData.filter((item) => {
      // Exclude detail rows and groups
      if (isDetailRow(item) || item.type === "group") return false;
      // If isRowSelectable is defined, use it to check if row is selectable
      if (isRowSelectable) {
        return isRowSelectable(item);
      }
      return true;
    });
  }, [flattenedData, isRowSelectable]);

  const allSelectableKeys = useMemo(() => {
    return new Set(selectableItems.map((item) => String(item.id)));
  }, [selectableItems]);

  const isAllSelected = useMemo(() => {
    if (allSelectableKeys.size === 0) return false;
    return Array.from(allSelectableKeys).every((key) => selectedKeys.has(key));
  }, [allSelectableKeys, selectedKeys]);

  const isSomeSelected = useMemo(() => {
    if (allSelectableKeys.size === 0) return false;
    return Array.from(allSelectableKeys).some((key) => selectedKeys.has(key)) && !isAllSelected;
  }, [allSelectableKeys, selectedKeys, isAllSelected]);

  const toggleSelectAll = () => {
    if (isAllSelected) {
      // Deselect all
      deselectAll();
    } else {
      // Select all selectable items
      const newSelection = new Set(allSelectableKeys);
      setSelectedKeys(newSelection);
      if (onSelectionChange) {
        onSelectionChange(newSelection);
      }
    }
  };

  // Pinned Detail Rows (translateX) logic
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [scrollLeft, setScrollLeft] = useState(0);
  const [isScrolled, setIsScrolled] = useState(false);

  const handleScroll = useCallback(() => {
    if (!scrollContainerRef.current) return;
    const x = scrollContainerRef.current.scrollLeft;
    setScrollLeft(x);
    setIsScrolled(x > 0);
  }, []);

  const updateScrollMetrics = useCallback(() => {
    if (!scrollContainerRef.current) return;
    setScrollLeft(scrollContainerRef.current.scrollLeft);
  }, []);

  useEffect(() => {
    window.addEventListener("resize", updateScrollMetrics);
    return () => window.removeEventListener("resize", updateScrollMetrics);
  }, [updateScrollMetrics]);

  useLayoutEffect(() => {
    updateScrollMetrics();
  }, [data, columns, updateScrollMetrics]);

  // SVG icons
  const ChevronUpIcon = () => (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="13"
      height="13"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="text-[#8690a6]"
    >
      <path d="m18 15-6-6-6 6" />
    </svg>
  );

  const ChevronDownIcon = () => (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="13"
      height="13"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="text-[#8690a6]"
    >
      <path d="m6 9 6 6 6-6" />
    </svg>
  );

  // Render cells for normal (non-group, non-detail) rows
  const renderNormalRowCells = (item: Item, rowIndex: number) => {
    const tds = columns.map((col, colIndex) => {
      return (
        <td
          key={`cell-${item.id}-${colIndex}`}
          className={cellPadding}
          style={{
            width: col.width || "auto",
            willChange: col.sticky ? "transform" : "auto",
          }}
          data-sticky={col.sticky ? "true" : "false"}
          data-depth={colIndex === 0 && item.__depth && item.__depth > 0 ? item.__depth : "0"}
        >
          {colIndex === 0 ? (
            <div className="flex items-center">
              <input
                checked={selectedKeys.has(String(item.id))}
                onClick={(e) => {
                  e.stopPropagation();
                  // Prevent click if row is not selectable
                  if (isRowSelectable && !isRowSelectable(item)) {
                    e.preventDefault();
                    return;
                  }
                }}
                onChange={(e) => {
                  // Prevent change if row is not selectable
                  if (isRowSelectable && !isRowSelectable(item)) {
                    e.preventDefault();
                    return;
                  }
                  toggleSelectRow(item);
                }}
                type="checkbox"
                disabled={isRowSelectable ? !isRowSelectable(item) : false}
                style={{
                  '--accent-color': '#4f46e5',
                } as React.CSSProperties}
                className={`mr-4 ml-1 ${
                  isRowSelectable && !isRowSelectable(item)
                    ? "opacity-50 cursor-not-allowed pointer-events-none"
                    : ""
                }`}
              />
              <div>{col.render(item, rowIndex)}</div>
              {showCaret && item.children && (
                <span className="ml-2">
                  {isExpanded(item.id) ? <ChevronDownIcon /> : <ChevronUpIcon />}
                </span>
              )}
            </div>
          ) : (
            col.render(item, rowIndex)
          )}
        </td>
      );
    });
    return tds;
  };

  const handleClear = () => {
    setSearchTerm("");
  };

  return (
    <div className={`relative space-y-3 ${className || ""}`}>
      {/* Search Input */}
      {!hideSearch && (
        <div className="relative flex items-center mb-4">
          <svg
            className="-translate-y-1/2 search-icon absolute top-1/2 left-4 h-[16px] w-[16px] text-[#8690a6]"
            xmlns="http://www.w3.org/2000/svg"
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            role="presentation"
          >
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.3-4.3" />
          </svg>

          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Type anything to search..."
            className="search-bar h-[50px] bg-white shadow-[0px_0px_2px_0px_rgba(41,41,51,.04),0px_8px_24px_0px_rgba(41,41,51,.12)] rounded-[12px] w-full text-[#0a0a0a] border-none px-3 py-2 pl-12 placeholder:text-[#8b8b8b] placeholder:text-[14px] placeholder:font-normal placeholder:tracking-normal focus:outline-none"
            onFocus={() => setIsSearchFocused(true)}
            onBlur={() => setIsSearchFocused(false)}
          />
          {searchTerm && (
            <button
              onClick={handleClear}
              className="-translate-y-1/2 absolute top-1/2 right-3 z-30 rounded-sm opacity-70 transition-opacity hover:opacity-100 p-0 h-auto"
            >
              <XIcon className="size-5 text-[#8b8b8b]" />
            </button>
          )}
        </div>
      )}

      <div
        ref={scrollContainerRef}
        className={`relative w-full max-h-[620px] overflow-auto scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-transparent rounded-[20px] bg-white border border-[#ebebeb] shadow-x1 ${isSearchFocused || searchTerm ? "searching" : ""}`}
        onScroll={handleScroll}
      >
        <table className="shadow-table min-h-[92px] w-full min-w-max border-collapse">
          <thead className="sticky top-0 z-[5] after:content-[''] after:absolute after:bottom-0 after:left-0 after:right-0 after:h-[1px] after:bg-[#f0f0f0]">
            {bulkActionsBar ? (
              <tr className="border-none">
                <th
                  colSpan={columns.length}
                  className="bg-white px-3 pt-[10px] pb-[10px] text-left sticky top-0"
                >
                  <div className="flex items-center gap-4 px-1">
                    <input
                      type="checkbox"
                      checked={isAllSelected}
                      ref={(el) => {
                        if (el) {
                          el.indeterminate = isSomeSelected;
                        }
                      }}
                      onChange={toggleSelectAll}
                      style={{
                        '--accent-color': '#4f46e5',
                      } as React.CSSProperties}
                      className="cursor-pointer"
                    />
                    {bulkActionsBar}
                  </div>
                </th>
              </tr>
            ) : (
              <tr className="border-none">
                {columns.map((col, colIndex) => (
                  <th
                    key={`header-${colIndex}`}
                    className="bg-white px-3 py-3 text-left sticky top-0"
                    style={{
                      width: col.width || "auto",
                      willChange: col.sticky ? "transform" : "auto",
                    }}
                    data-sticky={col.sticky ? "true" : "false"}
                  >
                    {colIndex === 0 ? (
                      <div className="flex items-center">
                        <input
                          type="checkbox"
                          checked={isAllSelected}
                          ref={(el) => {
                            if (el) {
                              el.indeterminate = isSomeSelected;
                            }
                          }}
                          onChange={toggleSelectAll}
                          disabled={allSelectableKeys.size === 0}
                          style={{
                            '--accent-color': '#4f46e5',
                          } as React.CSSProperties}
                          className={`mr-4 ml-1 ${
                            allSelectableKeys.size === 0
                              ? "opacity-50 cursor-not-allowed"
                              : "cursor-pointer"
                          }`}
                        />
                        <span className="text-[13px] tracking-[0.02em] font-light text-[#8b8b8b]">
                          {col.title}
                        </span>
                      </div>
                    ) : (
                      <span className="text-[13px] tracking-[0.02em] font-light text-[#8b8b8b]">
                        {col.title}
                      </span>
                    )}
                  </th>
                ))}
              </tr>
            )}
          </thead>
          <tbody>
            {flattenedData.map((item, index) => {
              const rowKey = getRowKey ? getRowKey(item, index) : `row-${item.id}`;
              const expanded = isExpanded(item.id);
              const hasChildren = item.children && item.children.length > 0;
              const detailRow = isDetailRow(item);
              const customRowClassName = getRowClassName ? getRowClassName(item, index) : "";
              const shouldShowRedLine = isRowSelectable && !isRowSelectable(item);
              return (
                <tr
                  key={rowKey}
                  className={`table-row ${
                    !detailRow && item.type !== "group" && index !== flattenedData.length - 1
                      ? "border-b border-[#f0f0f0]"
                      : ""
                  } ${
                    !detailRow && item.type !== "group" && onRowClick
                      ? "cursor-pointer hover:bg-[#f9fbfd]"
                      : ""
                  } ${customRowClassName} ${shouldShowRedLine ? "opacity-50 line-through" : ""}`}
                  data-border={
                    !detailRow && item.type !== "group" && index !== flattenedData.length - 1
                      ? "true"
                      : "false"
                  }
                  data-clickable={hasChildren && !detailRow ? "true" : "false"}
                  data-group={item.type === "group" ? "true" : "false"}
                  data-expanded={expanded ? "true" : "false"}
                  data-detail={detailRow ? "true" : "false"}
                  onClick={() => {
                    if (hasChildren && !detailRow) {
                      toggleExpand(item.id);
                    } else if (!detailRow && item.type !== "group" && onRowClick) {
                      onRowClick(item);
                    }
                  }}
                >
                  {renderNormalRowCells(item, index)}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
