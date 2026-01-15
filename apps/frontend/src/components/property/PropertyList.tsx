/**
 * Property list component with grid/list view
 */
import { useState } from "react";
import { Grid as GridIcon, List as ListIcon } from "lucide-react";
import { Grid } from "@mui/material";
import { Property } from "@/types";
import { PropertyCard } from "./PropertyCard";
import { EmptyState, LoadingSpinner } from "@/components/layout";
import { cn } from "@/lib/utils";

export interface PropertyListProps {
  properties: Property[];
  isLoading?: boolean;
  onSaveProperty?: (property: Property) => void;
  onRemoveProperty?: (property: Property) => void;
  savedPropertyIds?: number[];
  emptyMessage?: string;
  emptyAction?: React.ReactNode;
  className?: string;
}

type ViewMode = "grid" | "list";

const PropertyList = ({
  properties,
  isLoading,
  onSaveProperty,
  onRemoveProperty,
  savedPropertyIds = [],
  emptyMessage = "No properties found",
  emptyAction,
  className,
}: PropertyListProps) => {
  const [viewMode, setViewMode] = useState<ViewMode>("grid");

  if (isLoading) {
    return (
      <div className="py-12">
        <LoadingSpinner text="Loading properties..." />
      </div>
    );
  }

  if (properties.length === 0) {
    return (
      <EmptyState
        title={emptyMessage}
        description="Try adjusting your search criteria or browse recommended properties."
        action={emptyAction}
      />
    );
  }

  return (
    <div className={className}>
      {/* View Toggle */}
      <div className="flex items-center justify-between mb-6">
        <p className="text-sm text-neutral-600">
          {properties.length}{" "}
          {properties.length === 1 ? "property" : "properties"} found
        </p>

        <div className="flex gap-1 bg-neutral-100 p-1 rounded-lg">
          <button
            onClick={() => setViewMode("grid")}
            className={cn(
              "p-2 rounded-md transition-colors",
              viewMode === "grid"
                ? "bg-white shadow-sm text-neutral-900"
                : "text-neutral-600 hover:text-neutral-900"
            )}
          >
            <GridIcon className="w-4 h-4" />
          </button>
          <button
            onClick={() => setViewMode("list")}
            className={cn(
              "p-2 rounded-md transition-colors",
              viewMode === "list"
                ? "bg-white shadow-sm text-neutral-900"
                : "text-neutral-600 hover:text-neutral-900"
            )}
          >
            <ListIcon className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Properties Grid/List */}
      {viewMode === "grid" ? (
        <Grid container spacing={3}>
          {properties.map((property) => (
            <Grid  size={{ xs: 12, sm: 6, md: 4 }} key={property.id}>
              <PropertyCard
                property={property}
                onSave={onSaveProperty}
                onRemove={onRemoveProperty}
                isSaved={savedPropertyIds.includes(property.id)}
                variant="default"
              />
            </Grid>
          ))}
        </Grid>
      ) : (
        <div className="space-y-4">
          {properties.map((property) => (
            <PropertyCard
              key={property.id}
              property={property}
              onSave={onSaveProperty}
              onRemove={onRemoveProperty}
              isSaved={savedPropertyIds.includes(property.id)}
              variant="compact"
            />
          ))}
        </div>
      )}
    </div>
  );
};

export { PropertyList };
