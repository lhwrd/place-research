import { ReactNode } from "react";
import { Card, CardContent, Box, Typography, Chip } from "@mui/material";
import { LucideIcon } from "lucide-react";

interface EnrichmentCardProps {
  title: string;
  icon?: LucideIcon;
  cached?: boolean;
  children: ReactNode;
}

export const EnrichmentCard = ({
  title,
  icon: Icon,
  cached,
  children,
}: EnrichmentCardProps) => {
  return (
    <Card>
      <CardContent>
        <Box
          sx={{
            display: "flex",
            alignItems: "center",
            gap: 1,
            mb: 2,
          }}
        >
          {Icon && <Icon size={20} />}
          <Typography variant="h5" fontWeight="600">
            {title}
          </Typography>
          {cached && <Chip label="Cached" size="small" color="info" />}
        </Box>
        {children}
      </CardContent>
    </Card>
  );
};
