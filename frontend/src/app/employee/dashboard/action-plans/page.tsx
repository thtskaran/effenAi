import { prisma } from "@/lib/prisma";
import React from "react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CalendarIcon, CheckCircle2, Clock, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { format } from "date-fns";
import Link from "next/link";

type Priority = "HIGH" | "MEDIUM" | "LOW";
type Status = "COMPLETED" | "IN_PROGRESS" | "PENDING";

interface Action {
  id: string;
  // Add other action properties as needed
}

interface ActionPlan {
  id: string;
  title: string;
  description: string | null;
  priority: Priority;
  status: Status;
  startDate: Date | string;
  endDate: Date | string | null;
  employeeId: string;
  actions: Action[];
}

async function getActionPlans(): Promise<ActionPlan[]> {
  // Removed all session and authentication checks
  const actionPlans = await prisma.actionPlan.findMany({
    include: {
      actions: true,
    },
    orderBy: {
      startDate: "desc",
    },
  });

  return actionPlans;
}

function getPriorityColor(priority: Priority | string): string {
  switch (priority) {
    case "HIGH":
      return "text-red-500 bg-red-100";
    case "MEDIUM":
      return "text-amber-500 bg-amber-100";
    case "LOW":
      return "text-green-500 bg-green-100";
    default:
      return "text-gray-500 bg-gray-100";
  }
}

function getStatusIcon(status: Status | string): React.ReactNode {
  switch (status) {
    case "COMPLETED":
      return <CheckCircle2 className="h-4 w-4 text-green-500" />;
    case "IN_PROGRESS":
      return <Clock className="h-4 w-4 text-blue-500" />;
    case "PENDING":
      return <AlertTriangle className="h-4 w-4 text-amber-500" />;
    default:
      return null;
  }
}

export default async function ActionPlansPage() {
  const actionPlans = await getActionPlans();

  return (
    <div className="container mx-auto py-8">
      <Card className="mb-8">
        <CardHeader>
          <CardTitle className="text-2xl font-bold">Action Plans</CardTitle>
          <CardDescription>
            Manage and track your assigned action plans
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableCaption>A list of your action plans</TableCaption>
            <TableHeader>
              <TableRow>
                <TableHead>Title</TableHead>
                <TableHead>Priority</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Timeline</TableHead>
                <TableHead>Tasks</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {actionPlans.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-8">
                    No action plans found
                  </TableCell>
                </TableRow>
              ) : (
                actionPlans.map((plan) => (
                  <TableRow key={plan.id}>
                    <TableCell className="font-medium">
                      {plan.title}
                      {plan.description && (
                        <p className="text-sm text-gray-500 mt-1 line-clamp-1">
                          {plan.description}
                        </p>
                      )}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant="outline"
                        className={getPriorityColor(plan.priority)}
                      >
                        {plan.priority}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        {getStatusIcon(plan.status)}
                        <span>{plan.status}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <CalendarIcon className="h-4 w-4 text-gray-400" />
                        <div>
                          <p className="text-sm font-medium">
                            {format(new Date(plan.startDate), "MMM d, yyyy")}
                          </p>
                          {plan.endDate && (
                            <p className="text-xs text-gray-500">
                              Due:{" "}
                              {format(new Date(plan.endDate), "MMM d, yyyy")}
                            </p>
                          )}
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary">
                        {plan.actions.length} Tasks
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button asChild size="sm" variant="outline">
                        <Link
                          href={`/employee/dashboard/action-plans/${plan.id}`}
                        >
                          View Details
                        </Link>
                      </Button>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
