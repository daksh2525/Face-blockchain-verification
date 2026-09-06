// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/// @title ContentVerification
/// @notice Stores SHA-256 content fingerprints on-chain so that anyone can
///         later verify whether a piece of content matches what was
///         originally registered, without ever storing the content itself.
/// @dev IMPORTANT: this contract stores a CONTENT HASH (the SHA-256 fingerprint
///      of some off-chain content, e.g. an image). This is NOT the same thing
///      as a TRANSACTION HASH. A transaction hash identifies the blockchain
///      transaction that called registerContent(); the content hash identifies
///      the actual off-chain content being verified. Do not confuse the two.
contract ContentVerification {

    struct ContentRecord {
        bool exists;            // whether this hash has been registered
        address submitter;      // who registered it
        uint256 timestamp;      // block timestamp at registration
        string sourceReference; // e.g. a source URL or compact reference string
    }

    // contentHash => record
    mapping(bytes32 => ContentRecord) private records;

    /// @notice Emitted whenever a new content hash is successfully registered.
    /// @param contentHash The SHA-256 fingerprint of the registered content.
    /// @param submitter The address that registered the content.
    /// @param timestamp The block timestamp at registration.
    event ContentRegistered(
        bytes32 indexed contentHash,
        address indexed submitter,
        uint256 timestamp
    );

    /// @notice Registers a new content hash on-chain.
    /// @dev Reverts if this exact hash has already been registered, to
    ///      prevent unnecessary duplicate registrations (and duplicate gas
    ///      spend) for content that's already on record.
    /// @param contentHash The SHA-256 hash of the content being registered.
    /// @param sourceReference A human-readable reference (e.g. source URL).
    function registerContent(bytes32 contentHash, string calldata sourceReference) external {
        require(contentHash != bytes32(0), "Content hash cannot be zero");
        require(!records[contentHash].exists, "Content hash already registered");

        records[contentHash] = ContentRecord({
            exists: true,
            submitter: msg.sender,
            timestamp: block.timestamp,
            sourceReference: sourceReference
        });

        emit ContentRegistered(contentHash, msg.sender, block.timestamp);
    }

    /// @notice Checks whether a given content hash is registered on-chain.
    /// @param contentHash The hash to check.
    /// @return isVerified True if this exact hash was found registered.
    function verifyContent(bytes32 contentHash) external view returns (bool isVerified) {
        return records[contentHash].exists;
    }

    /// @notice Retrieves the full stored record for a given content hash.
    /// @param contentHash The hash to look up.
    /// @return exists Whether a record was found.
    /// @return submitter The address that registered it (zero address if not found).
    /// @return timestamp The block timestamp of registration (0 if not found).
    /// @return sourceReference The source reference string (empty if not found).
    function getRecord(bytes32 contentHash)
        external
        view
        returns (
            bool exists,
            address submitter,
            uint256 timestamp,
            string memory sourceReference
        )
    {
        ContentRecord storage record = records[contentHash];
        return (record.exists, record.submitter, record.timestamp, record.sourceReference);
    }
}