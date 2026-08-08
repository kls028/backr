import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'

export function NotFoundPage() {
  return (
    <div className="flex flex-col items-start gap-4">
      <h1 className="text-3xl font-semibold tracking-tight">Not found</h1>
      <p className="text-muted-foreground">That route does not exist.</p>
      <Button asChild variant="secondary">
        <Link to="/">Go home</Link>
      </Button>
    </div>
  )
}
