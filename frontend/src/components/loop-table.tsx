"use client";
"use no memo";

import { useEffect, useState } from "react";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  createColumnHelper,
  SortingState,
  flexRender,
} from "@tanstack/react-table";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  getLooping,
  getAssets,
  getProtocols,
  LoopOpportunityOut,
} from "@/lib/api";

const columnHelper = createColumnHelper<LoopOpportunityOut>();

function fmtPct(v: number | null | undefined): string {
  if (v == null) return "—";
  return v.toFixed(2) + "%";
}

const columns = [
  columnHelper.accessor("protocol", {
    header: "Protocol",
    cell: (info) => info.getValue(),
  }),
  columnHelper.accessor("asset", {
    header: "Asset",
    cell: (info) => info.getValue(),
  }),
  columnHelper.accessor("deposit_apy", {
    header: "Deposit APY",
    cell: (info) => fmtPct(info.getValue()),
  }),
  columnHelper.accessor("borrow_apy", {
    header: "Borrow APY",
    cell: (info) => fmtPct(info.getValue()),
  }),
  columnHelper.accessor("effective_yield", {
    header: "Effective Yield",
    cell: (info) => fmtPct(info.getValue()),
    sortingFn: "basic",
  }),
  columnHelper.accessor("score", {
    header: "Score",
    cell: (info) => info.getValue().toFixed(2),
    sortingFn: "basic",
  }),
];

export default function LoopTable() {
  const [data, setData] = useState<LoopOpportunityOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [assetFilter, setAssetFilter] = useState("");
  const [protocolFilter, setProtocolFilter] = useState("");
  const [minYield, setMinYield] = useState("");
  const [minLiquidity, setMinLiquidity] = useState("");

  // Dropdown options
  const [assets, setAssets] = useState<string[]>([]);
  const [protocols, setProtocols] = useState<string[]>([]);

  // Sorting
  const [sorting, setSorting] = useState<SortingState>([
    { id: "effective_yield", desc: true },
  ]);

  // Fetch dropdown options on mount
  useEffect(() => {
    getAssets().then(setAssets).catch(() => {});
    getProtocols().then((p) => setProtocols(p.map((x) => x.name))).catch(() => {});
  }, []);

  // Fetch data when filters change
  useEffect(() => {
    setLoading(true);
    setError(null);
    const params: Record<string, string | number> = { limit: 50 };
    if (assetFilter) params.asset = assetFilter;
    if (protocolFilter) params.protocol = protocolFilter;
    if (minYield) params.min_yield = Number(minYield);
    if (minLiquidity) params.min_liquidity = Number(minLiquidity);

    getLooping(params)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [assetFilter, protocolFilter, minYield, minLiquidity]);

  // eslint-disable-next-line react-hooks/incompatible-library -- TanStack Table is designed for React 19, false positive
  const table = useReactTable({
    data,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <div className="space-y-4">
      {/* Filter bar */}
      <div className="flex flex-wrap items-end gap-3">
        <div className="space-y-1">
          <label className="text-xs font-medium text-muted-foreground">
            Asset
          </label>
          <Select value={assetFilter} onValueChange={(v) => setAssetFilter(v ? (v === "all" ? "" : v) : "")}>
            <SelectTrigger className="w-36">
              <SelectValue placeholder="All Assets" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Assets</SelectItem>
              {assets.map((a) => (
                <SelectItem key={a} value={a}>
                  {a}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1">
          <label className="text-xs font-medium text-muted-foreground">
            Protocol
          </label>
          <Select value={protocolFilter} onValueChange={(v) => setProtocolFilter(v ? (v === "all" ? "" : v) : "")}>
            <SelectTrigger className="w-36">
              <SelectValue placeholder="All Protocols" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Protocols</SelectItem>
              {protocols.map((p) => (
                <SelectItem key={p} value={p}>
                  {p}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1">
          <label className="text-xs font-medium text-muted-foreground">
            Min Yield (%)
          </label>
          <Input
            type="number"
            value={minYield}
            onChange={(e) => setMinYield(e.target.value)}
            placeholder="0"
            className="w-28"
          />
        </div>

        <div className="space-y-1">
          <label className="text-xs font-medium text-muted-foreground">
            Min Liquidity
          </label>
          <Input
            type="number"
            value={minLiquidity}
            onChange={(e) => setMinLiquidity(e.target.value)}
            placeholder="0"
            className="w-32"
          />
        </div>
      </div>

      {/* Table */}
      {loading && (
        <div className="py-8 text-center text-sm text-muted-foreground">
          Loading…
        </div>
      )}
      {error && (
        <div className="py-8 text-center text-sm text-destructive">{error}</div>
      )}
      {!loading && !error && data.length === 0 && (
        <div className="py-8 text-center text-sm text-muted-foreground">
          No loop opportunities found.
        </div>
      )}
      {!loading && !error && data.length > 0 && (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              {table.getHeaderGroups().map((hg) => (
                <TableRow key={hg.id}>
                  {hg.headers.map((header) => (
                    <TableHead
                      key={header.id}
                      className={
                        header.column.getCanSort()
                          ? "cursor-pointer select-none"
                          : ""
                      }
                      onClick={header.column.getToggleSortingHandler()}
                    >
                      {flexRender(
                        header.column.columnDef.header,
                        header.getContext()
                      )}
                      {{
                        asc: " ↑",
                        desc: " ↓",
                      }[header.column.getIsSorted() as string] ?? ""}
                    </TableHead>
                  ))}
                </TableRow>
              ))}
            </TableHeader>
            <TableBody>
              {table.getRowModel().rows.map((row) => (
                <TableRow key={row.id}>
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext()
                      )}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
