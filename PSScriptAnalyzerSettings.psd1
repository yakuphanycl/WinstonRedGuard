@{
    Rules = @{
        PSUseShouldProcessForStateChangingFunctions = @{
            Enable = $true
        }
        PSAvoidGlobalVars = @{
            Enable = $true
        }
        PSUseDeclaredVarsMoreThanAssignments = @{
            Enable = $true
        }
    }
    Severity = @("Warning", "Error")
    ExcludeRules = @(
        "PSAvoidUsingWriteHost"
    )
}
