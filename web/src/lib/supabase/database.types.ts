
export type Json = string | number | boolean | null | { [key: string]: Json | undefined } | Json[]

export type Database = {
  
  "public": {
          Tables: {
            "accounts": {
                  Row: {
                    "archived": boolean,"currency": string,"id": string,"kind": string,"name": string,"opening_balance": number,"user_id": string
                  }
                  ComputedFields: never
                  Insert: {
                    "archived"?: boolean,"currency": string,"id"?: string,"kind": string,"name": string,"opening_balance"?: number,"user_id": string
                  }
                  Update: {
                    "archived"?: boolean,"currency"?: string,"id"?: string,"kind"?: string,"name"?: string,"opening_balance"?: number,"user_id"?: string
                  }
                  Relationships: [
                    {
      foreignKeyName: "accounts_user_id_fkey"
      columns: ["user_id"]
isOneToOne: false
      referencedRelation: "users"
      referencedColumns: ["id"]
    }
                  ]
                },"categories": {
                  Row: {
                    "id": string,"kind": string,"name": string,"user_id": string | null
                  }
                  ComputedFields: never
                  Insert: {
                    "id"?: string,"kind": string,"name": string,"user_id"?: string | null
                  }
                  Update: {
                    "id"?: string,"kind"?: string,"name"?: string,"user_id"?: string | null
                  }
                  Relationships: [
                    {
      foreignKeyName: "categories_user_id_fkey"
      columns: ["user_id"]
isOneToOne: false
      referencedRelation: "users"
      referencedColumns: ["id"]
    }
                  ]
                },"corrections": {
                  Row: {
                    "created_at": string,"field": string,"id": string,"new_value": string,"old_value": string | null,"raw_text": string,"transaction_id": string | null,"user_id": string
                  }
                  ComputedFields: never
                  Insert: {
                    "created_at"?: string,"field": string,"id"?: string,"new_value": string,"old_value"?: string | null,"raw_text": string,"transaction_id"?: string | null,"user_id": string
                  }
                  Update: {
                    "created_at"?: string,"field"?: string,"id"?: string,"new_value"?: string,"old_value"?: string | null,"raw_text"?: string,"transaction_id"?: string | null,"user_id"?: string
                  }
                  Relationships: [
                    {
      foreignKeyName: "corrections_transaction_id_fkey"
      columns: ["transaction_id"]
isOneToOne: false
      referencedRelation: "transactions"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "corrections_user_id_fkey"
      columns: ["user_id"]
isOneToOne: false
      referencedRelation: "users"
      referencedColumns: ["id"]
    }
                  ]
                },"exchange_rates": {
                  Row: {
                    "currency": string,"fetched_at": string,"id": number,"source": string,"usd_per_unit": number
                  }
                  ComputedFields: never
                  Insert: {
                    "currency": string,"fetched_at"?: string,"id"?: never,"source": string,"usd_per_unit": number
                  }
                  Update: {
                    "currency"?: string,"fetched_at"?: string,"id"?: never,"source"?: string,"usd_per_unit"?: number
                  }
                  Relationships: [
                    
                  ]
                },"exchanges": {
                  Row: {
                    "created_at": string,"deleted_at": string | null,"effective_rate": number,"from_account_id": string,"from_amount": number,"id": string,"occurred_at": string,"raw_text": string | null,"reference_rate": number | null,"to_account_id": string,"to_amount": number,"user_id": string
                  }
                  ComputedFields: never
                  Insert: {
                    "created_at"?: string,"deleted_at"?: string | null,"effective_rate": number,"from_account_id": string,"from_amount": number,"id"?: string,"occurred_at"?: string,"raw_text"?: string | null,"reference_rate"?: number | null,"to_account_id": string,"to_amount": number,"user_id": string
                  }
                  Update: {
                    "created_at"?: string,"deleted_at"?: string | null,"effective_rate"?: number,"from_account_id"?: string,"from_amount"?: number,"id"?: string,"occurred_at"?: string,"raw_text"?: string | null,"reference_rate"?: number | null,"to_account_id"?: string,"to_amount"?: number,"user_id"?: string
                  }
                  Relationships: [
                    {
      foreignKeyName: "exchanges_from_account_id_user_id_fkey"
      columns: ["from_account_id","user_id"]
isOneToOne: false
      referencedRelation: "account_balances"
      referencedColumns: ["account_id","user_id"]
    },{
      foreignKeyName: "exchanges_from_account_id_user_id_fkey"
      columns: ["from_account_id","user_id"]
isOneToOne: false
      referencedRelation: "accounts"
      referencedColumns: ["id","user_id"]
    },{
      foreignKeyName: "exchanges_to_account_id_user_id_fkey"
      columns: ["to_account_id","user_id"]
isOneToOne: false
      referencedRelation: "account_balances"
      referencedColumns: ["account_id","user_id"]
    },{
      foreignKeyName: "exchanges_to_account_id_user_id_fkey"
      columns: ["to_account_id","user_id"]
isOneToOne: false
      referencedRelation: "accounts"
      referencedColumns: ["id","user_id"]
    },{
      foreignKeyName: "exchanges_user_id_fkey"
      columns: ["user_id"]
isOneToOne: false
      referencedRelation: "users"
      referencedColumns: ["id"]
    }
                  ]
                },"link_codes": {
                  Row: {
                    "code": string,"created_at": string,"expires_at": string,"used_at": string | null,"user_id": string
                  }
                  ComputedFields: never
                  Insert: {
                    "code": string,"created_at"?: string,"expires_at": string,"used_at"?: string | null,"user_id": string
                  }
                  Update: {
                    "code"?: string,"created_at"?: string,"expires_at"?: string,"used_at"?: string | null,"user_id"?: string
                  }
                  Relationships: [
                    {
      foreignKeyName: "link_codes_user_id_fkey"
      columns: ["user_id"]
isOneToOne: false
      referencedRelation: "users"
      referencedColumns: ["id"]
    }
                  ]
                },"processed_updates": {
                  Row: {
                    "bot_id": number,"received_at": string,"update_id": number
                  }
                  ComputedFields: never
                  Insert: {
                    "bot_id": number,"received_at"?: string,"update_id": number
                  }
                  Update: {
                    "bot_id"?: number,"received_at"?: string,"update_id"?: number
                  }
                  Relationships: [
                    
                  ]
                },"transactions": {
                  Row: {
                    "account_id": string,"amount": number,"amount_usd": number,"category_id": string | null,"created_at": string,"currency": string,"deleted_at": string | null,"description": string | null,"id": string,"kind": string,"occurred_at": string,"parse_confidence": number | null,"rate_source": string,"raw_text": string | null,"usd_per_unit": number,"user_id": string
                  }
                  ComputedFields: never
                  Insert: {
                    "account_id": string,"amount": number,"amount_usd": number,"category_id"?: string | null,"created_at"?: string,"currency": string,"deleted_at"?: string | null,"description"?: string | null,"id"?: string,"kind": string,"occurred_at"?: string,"parse_confidence"?: number | null,"rate_source": string,"raw_text"?: string | null,"usd_per_unit": number,"user_id": string
                  }
                  Update: {
                    "account_id"?: string,"amount"?: number,"amount_usd"?: number,"category_id"?: string | null,"created_at"?: string,"currency"?: string,"deleted_at"?: string | null,"description"?: string | null,"id"?: string,"kind"?: string,"occurred_at"?: string,"parse_confidence"?: number | null,"rate_source"?: string,"raw_text"?: string | null,"usd_per_unit"?: number,"user_id"?: string
                  }
                  Relationships: [
                    {
      foreignKeyName: "transactions_account_id_user_id_currency_fkey"
      columns: ["account_id","user_id","currency"]
isOneToOne: false
      referencedRelation: "account_balances"
      referencedColumns: ["account_id","user_id","currency"]
    },{
      foreignKeyName: "transactions_account_id_user_id_currency_fkey"
      columns: ["account_id","user_id","currency"]
isOneToOne: false
      referencedRelation: "accounts"
      referencedColumns: ["id","user_id","currency"]
    },{
      foreignKeyName: "transactions_category_id_fkey"
      columns: ["category_id"]
isOneToOne: false
      referencedRelation: "categories"
      referencedColumns: ["id"]
    },{
      foreignKeyName: "transactions_user_id_fkey"
      columns: ["user_id"]
isOneToOne: false
      referencedRelation: "users"
      referencedColumns: ["id"]
    }
                  ]
                },"users": {
                  Row: {
                    "auth_user_id": string | null,"created_at": string,"default_currency": string,"display_name": string | null,"id": string,"onboarded_at": string | null,"telegram_id": number,"timezone": string,"ves_rate_source": string
                  }
                  ComputedFields: never
                  Insert: {
                    "auth_user_id"?: string | null,"created_at"?: string,"default_currency"?: string,"display_name"?: string | null,"id"?: string,"onboarded_at"?: string | null,"telegram_id": number,"timezone"?: string,"ves_rate_source"?: string
                  }
                  Update: {
                    "auth_user_id"?: string | null,"created_at"?: string,"default_currency"?: string,"display_name"?: string | null,"id"?: string,"onboarded_at"?: string | null,"telegram_id"?: number,"timezone"?: string,"ves_rate_source"?: string
                  }
                  Relationships: [
                    
                  ]
                },"weekly_summaries": {
                  Row: {
                    "sent_at": string,"user_id": string,"week_start": string
                  }
                  ComputedFields: never
                  Insert: {
                    "sent_at"?: string,"user_id": string,"week_start": string
                  }
                  Update: {
                    "sent_at"?: string,"user_id"?: string,"week_start"?: string
                  }
                  Relationships: [
                    {
      foreignKeyName: "weekly_summaries_user_id_fkey"
      columns: ["user_id"]
isOneToOne: false
      referencedRelation: "users"
      referencedColumns: ["id"]
    }
                  ]
                }
          }
          Views: {
            "account_balances": {
                  Row: {
                    "account_id": string | null,"balance": number | null,"currency": string | null,"name": string | null,"user_id": string | null
                  }
                  ComputedFields: never
                  Insert: {
                           "account_id"?: string | null,"balance"?: never,"currency"?: string | null,"name"?: string | null,"user_id"?: string | null
                         }
                        Update: {
                           "account_id"?: string | null,"balance"?: never,"currency"?: string | null,"name"?: string | null,"user_id"?: string | null
                         }
                        Relationships: [
                    {
      foreignKeyName: "accounts_user_id_fkey"
      columns: ["user_id"]
isOneToOne: false
      referencedRelation: "users"
      referencedColumns: ["id"]
    }
                  ]
                },"account_balances_usd": {
                  Row: {
                    "account_id": string | null,"balance": number | null,"balance_usd": number | null,"currency": string | null,"name": string | null,"rate_fetched_at": string | null,"rate_source": string | null,"rate_stale": boolean | null,"usd_per_unit": number | null
                  }
                  ComputedFields: never
                  Relationships: [
                    
                  ]
                },"exchange_history": {
                  Row: {
                    "difference_pct": number | null,"effective_rate": number | null,"from_account": string | null,"from_amount": number | null,"from_currency": string | null,"id": string | null,"occurred_at": string | null,"reference_rate": number | null,"to_account": string | null,"to_amount": number | null,"to_currency": string | null
                  }
                  ComputedFields: never
                  Relationships: [
                    
                  ]
                },"latest_rates": {
                  Row: {
                    "currency": string | null,"fetched_at": string | null,"source": string | null,"usd_per_unit": number | null
                  }
                  ComputedFields: never
                  Relationships: [
                    
                  ]
                }
          }
          Functions: {
            "app_user_id":
{ Args: Record<PropertyKey, never>; Returns: string
                           },
"bolivar_rates":
{ Args: { "p_days"?: number }; Returns: {
              "day": string,"source": string,"usd_per_unit": number
            }[]
                           },
"edit_transaction":
{ Args: { "p_account_id": string,"p_amount": number,"p_category_id": string,"p_id": string,"p_kind": string }; Returns: number
                           },
"list_transactions":
{ Args: { "p_category_id"?: string,"p_currency"?: string,"p_from"?: string,"p_kind"?: string,"p_limit"?: number,"p_offset"?: number,"p_to"?: string }; Returns: {
              "account_id": string,"account_name": string,"amount": number,"amount_usd": number,"category_id": string,"category_name": string,"currency": string,"description": string,"edited": boolean,"id": string,"kind": string,"occurred_at": string,"rate_source": string,"total": number
            }[]
                           },
"local_day_start":
{ Args: { "p_day": string }; Returns: string
                           },
"redeem_link_code":
{ Args: { "p_code": string }; Returns: string
                           },
"spending_by_category":
{ Args: { "p_from": string,"p_to": string }; Returns: {
              "category": string,"movements": number,"total_usd": number
            }[]
                           },
"spending_by_week":
{ Args: { "p_weeks"?: number }; Returns: {
              "expenses_usd": number,"income_usd": number,"week_start": string
            }[]
                           }
          }
          Enums: {
            [_ in never]: never
          }
          CompositeTypes: {
            [_ in never]: never
          }
        }
}

type DatabaseWithoutInternals = Omit<Database, '__InternalSupabase'>

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never = never
> = DefaultSchemaTableNameOrOptions extends { schema: keyof DatabaseWithoutInternals }
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
  ? (DefaultSchema["Tables"] & DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
      Row: infer R
    }
    ? R
    : never
  : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never
> = DefaultSchemaTableNameOrOptions extends { schema: keyof DatabaseWithoutInternals }
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
  ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
      Insert: infer I
    }
    ? I
    : never
  : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never
> = DefaultSchemaTableNameOrOptions extends { schema: keyof DatabaseWithoutInternals }
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
  ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
      Update: infer U
    }
    ? U
    : never
  : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never = never
> = DefaultSchemaEnumNameOrOptions extends { schema: keyof DatabaseWithoutInternals }
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
  ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
  : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never = never
> = PublicCompositeTypeNameOrOptions extends { schema: keyof DatabaseWithoutInternals }
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
  ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
  : never

export const Constants = {
  "public": {
          Enums: {
            
          }
        }
} as const
