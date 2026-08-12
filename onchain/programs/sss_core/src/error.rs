use anchor_lang::prelude::*;

#[error_code]
pub enum ErrorCode {
    #[msg("Only the counter authority can update this counter")]
    Unauthorized,
    #[msg("Counter has reached the maximum value")]
    CounterOverflow,
    #[msg("Campaign dates or goals are invalid")]
    InvalidCampaignTerms,
    #[msg("The campaign USDC mint is invalid")]
    InvalidUsdcMint,
    #[msg("Stretch goals must be strictly increasing")]
    InvalidGoalOrder,
    #[msg("Campaign has too many stretch goals")]
    TooManyStretchGoals,
    #[msg("Campaign metadata URI is too long")]
    MetadataUriTooLong,
    #[msg("Campaign is not accepting subscriptions")]
    CampaignNotOpen,
    #[msg("Purchase units must be positive")]
    InvalidPurchaseUnits,
    #[msg("Campaign arithmetic overflowed")]
    ArithmeticOverflow,
    #[msg("The supplied SPL Token program is invalid")]
    InvalidTokenProgram,
    #[msg("Only the campaign creator can settle the campaign")]
    UnauthorizedSettlement,
    #[msg("Campaign has not reached its success threshold")]
    ThresholdNotReached,
    #[msg("Campaign is not ready for settlement")]
    SettlementNotReady,
    #[msg("Invalid Subscription Plan Price")]
    InvalidSubscriptionPlanPrice,
    #[msg("Subscription Plan is inactive")]
    InactiveSubscriptionPlan,
}
