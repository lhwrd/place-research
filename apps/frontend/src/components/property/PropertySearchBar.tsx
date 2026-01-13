/**
 * Property search bar component
 */
import { useState } from "react";
import { Search, MapPin } from "lucide-react";
import { Button } from "@mui/material";
import { TextField } from "@mui/material";
import { cn } from "@/lib/utils";

export interface PropertySearchBarProps {
  onSearch: (address: string) => void;
  isLoading?: boolean;
  placeholder?: string;
  className?: string;
}

const PropertySearchBar = ({
  onSearch,
  isLoading,
  placeholder = "Enter property address...",
  className,
}: PropertySearchBarProps) => {
  const [address, setAddress] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (address.trim()) {
      onSearch(address.trim());
    }
  };

  return (
    <form onSubmit={handleSubmit} className={cn("w-full", className)}>
      <div className="flex gap-3">
        <div className="flex-1 relative">
          <TextField
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            placeholder={placeholder}
            disabled={isLoading}
            fullWidth
            variant="outlined"
            InputProps={{
              startAdornment: (
                <MapPin className="w-5 h-5 text-neutral-400 mr-2" />
              ),
            }}
          />
        </div>
        <Button
          type="submit"
          variant="contained"
          size="large"
          disabled={!address.trim() || isLoading}
        >
          {isLoading ? (
            <>
              <span className="animate-spin mr-2">⏳</span>
              Searching...
            </>
          ) : (
            <>
              <Search className="w-5 h-5 mr-2" />
              Search
            </>
          )}
        </Button>
      </div>
    </form>
  );
};

export { PropertySearchBar };
