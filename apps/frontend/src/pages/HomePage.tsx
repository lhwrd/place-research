import { Building2, Search, Database } from "lucide-react";
import { Box, Typography, Card, CardContent, Chip } from "@mui/material";

interface FeatureCardProps {
  icon: React.ReactNode;
  title: string;
  description: string;
}

const FeatureCard: React.FC<FeatureCardProps> = ({
  icon,
  title,
  description,
}) => {
  return (
    <Card
      sx={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        p: 3,
        boxShadow: 1,
        "&:hover": {
          boxShadow: 3,
        },
        transition: "box-shadow 0.3s",
      }}
    >
      <CardContent sx={{ textAlign: "center", p: 0 }}>
        <Box
          sx={{
            mb: 2,
            p: 1.5,
            bgcolor: "grey.100",
            borderRadius: "50%",
            display: "inline-flex",
          }}
        >
          {icon}
        </Box>
        <Typography variant="h6" fontWeight="600" mb={1} color="text.primary">
          {title}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {description}
        </Typography>
      </CardContent>
    </Card>
  );
};

export const HomePage: React.FC = () => {
  return (
    <Box sx={{ py: 4 }}>
      {/* Hero Section */}
      <Box sx={{ textAlign: "center", mb: 8 }}>
        <Typography variant="h2" fontWeight="bold" color="text.primary" mb={2}>
          Place Research
        </Typography>
        <Typography
          variant="h5"
          color="text.secondary"
          sx={{ maxWidth: 800, mx: "auto" }}
        >
          Comprehensive residential property data and insights at your
          fingertips
        </Typography>
      </Box>

      {/* Features Grid */}
      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: { xs: "1fr", md: "repeat(3, 1fr)" },
          gap: 4,
          maxWidth: 1000,
          mx: "auto",
        }}
      >
        <FeatureCard
          icon={<Search style={{ width: 32, height: 32, color: "#424242" }} />}
          title="Address Search"
          description="Search for any residential property by address and get detailed information"
        />
        <FeatureCard
          icon={
            <Database style={{ width: 32, height: 32, color: "#424242" }} />
          }
          title="Data Enrichment"
          description="Access enriched property data from multiple trusted sources"
        />
        <FeatureCard
          icon={
            <Building2 style={{ width: 32, height: 32, color: "#424242" }} />
          }
          title="Property Insights"
          description="Get comprehensive insights about neighborhoods and property values"
        />
      </Box>

      {/* Coming Soon Badge */}
      <Box sx={{ textAlign: "center", mt: 8 }}>
        <Chip
          label="Coming Soon"
          sx={{
            bgcolor: "primary.main",
            color: "white",
            fontWeight: 500,
            px: 2,
            py: 1,
          }}
        />
      </Box>
    </Box>
  );
};
