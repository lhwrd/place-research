import { cn } from "@/lib/utils";

interface LoadingSpinnerProps {
  size?: "sm" | "md" | "lg";
  className?: string;
  text?: string;
}

const sizeClasses = {
  sm: "h-4 w-4 border-2",
  md: "h-8 w-8 border-2",
  lg: "h-12 w-12 border-3",
};

export const LoadingSpinner = ({
  size = "md",
  className,
  text,
}: LoadingSpinnerProps) => {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3",
        className
      )}
    >
      <div
        className={cn(
          "animate-spin rounded-full border-neutral-900 border-t-transparent",
          sizeClasses[size]
        )}
      />
      {text && <p className="text-sm text-neutral-600">{text}</p>}
    </div>
  );
};
