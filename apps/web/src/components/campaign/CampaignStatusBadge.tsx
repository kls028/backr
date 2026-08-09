import { Badge } from '@/components/ui/badge'

export function CampaignStatusBadge({ status }: { status: string }) {
  return <Badge variant={status === 'cancelled' ? 'destructive' : 'secondary'}>{status}</Badge>
}
